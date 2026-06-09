import os
import json
import re
import certifi
from typing import TypedDict, Any, Dict, List
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama

load_dotenv()

mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    mongo_uri = "mongodb://localhost:27017"
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
db = client.enterprise_loans_db
db_collection = db.loan_applications

class AgentState(TypedDict):
    user_query: str
    metadata_schema: str
    shadow_query_str: str
    mongo_query_dict: Any
    database_results: List[Dict[str, Any]]
    project_fields: List[str]
    is_count_query: bool
    error_message: str
    retry_count: int
    final_output_text: str

def flatten_dict(d: dict, parent_key: str = '', sep: str = ' -> ') -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def render_ascii_table(flat_docs: List[dict]) -> str:
    if not flat_docs:
        return "No records found."
    keys = sorted(list(set(k for doc in flat_docs for k in doc.keys())))
    widths = {k: len(k) for k in keys}
    for doc in flat_docs:
        for k in keys:
            widths[k] = max(widths[k], len(str(doc.get(k, ""))))
    header = " | ".join(f"{k:<{widths[k]}}" for k in keys)
    separator = "-+-".join("-" * widths[k] for k in keys)
    lines = [separator, header, separator]
    for doc in flat_docs:
        row_str = " | ".join(f"{str(doc.get(k, '')):<{widths[k]}}" for k in keys)
        lines.append(row_str)
    lines.append(separator)
    return "\n".join(lines)

def schema_extractor_node(state: AgentState) -> Dict[str, Any]:
    print("Node 1: Loading Hardcoded Database Schema...")
    schema = {
        "application_id": "string",
        "status": "string",
        "requested_amount": "number",
        "term_months": "number",
        "financials.annual_income": "number",
        "financials.credit_score": "number",
        "financials.existing_debt": "number",
        "customer.first_name": "string",
        "customer.last_name": "string",
        "customer.email": "string",
        "customer.phone": "string",
        "customer.address.street": "string",
        "customer.address.city": "string",
        "customer.address.state": "string",
        "customer.address.zip": "string"
    }
    schema_context = "DATABASE SCHEMA METADATA:\n"
    for k, v in schema.items():
        schema_context += f"- '{k}': data type is {v}\n"
    return {"metadata_schema": schema_context}

def translator_node(state: AgentState) -> Dict[str, Any]:
    print("Node 2: Translating Natural Language Query to MongoDB MQL...")
    schema_prompt = state["metadata_schema"]
    error_feedback = ""
    if state.get("error_message"):
        print(f"Self-Healing Active. Previous Error: {state['error_message']}")
        error_feedback = f"\nYOUR PREVIOUS TRANSLATION ATTEMPT FAILED WITH THIS ERROR:\n{state['error_message']}\nFix your JSON filter structure mapping parameters accordingly."

    system_instructions = (
        "You are an isolated database compiler translating natural language queries to MongoDB filter JSON.\n"
        "Generate absolute raw valid JSON matching standard key filter targets. Do NOT write markdown code blocks or wrap in ```json.\n"
        f"{schema_prompt}\n"
        "RULES:\n"
        "1. Identify the condition fields in the query.\n"
        "2. Output a MongoDB query filter JSON object mapping fields to their values.\n"
        "3. ONLY filter on the actual conditions/constants in the query, not the fields being requested/displayed.\n"
        "4. For numeric or value checks, use NoSQL operators: '$lt', '$gt', '$ne', or '$in'.\n"
        "5. If the query asks for grouping, group-by aggregates, averages, or counts (e.g. 'average requested amount by status', 'count by state'), you MUST output a standard MongoDB aggregation pipeline (a list of stages) containing a '$group' stage.\n"
        "6. If the user query is purely conversational, greeting-based, or completely unrelated to any database entities/intent (e.g. 'hello', 'how are you?', etc.), you MUST output: {\"error\": \"unrelated_query\"}.\n"
        "7. If the user query asks for specific fields (e.g. 'what is the status of...', 'give name of...', 'phone number of...'), include a special key '$project' containing a list of those requested fields (e.g., [\"customer.first_name\", \"status\"]).\n"
        "8. If the user query asks for the 'number of' or 'count of' records (e.g. 'how many applications are approved', 'count of...'), include a special key '$count': true. Do NOT include '$count': true for general search requests.\n"
        "9. To find maximum, minimum, highest, lowest, or sorted values across all documents, output a JSON object with special keys:\n"
        "   - \"$query\": the filter conditions (or {} if none).\n"
        "   - \"$sort\": the field key to sort by, mapped to -1 for descending (maximum/highest) or 1 for ascending (minimum/lowest).\n"
        "   - \"$limit\": 1.\n"
        "10. For fuzzy terms like 'about' or 'around' for a numeric field, output a reasonable range (e.g. for credit score 'about 750' use $gte 720 and $lte 780). Do NOT append a '$count': true key for fuzzy range queries unless explicitly requested.\n"
        "11. When a query references a full name (first name and last name, e.g., 'Deepak Sharma', 'Priya Patel'), you MUST split the name into first name and last name and filter on BOTH keys in your output JSON (e.g., {\"customer.first_name\": \"Deepak\", \"customer.last_name\": \"Sharma\"}).\n\n"
        "EXAMPLES:\n"
        "Input: What is the status of the loan application for Rohan Sharma?\n"
        "Output: {\"customer.first_name\": \"Rohan\", \"customer.last_name\": \"Sharma\", \"$project\": [\"application_id\", \"status\"]}\n\n"
        "Input: Give me only the phone number of Deepak Sharma.\n"
        "Output: {\"customer.first_name\": \"Deepak\", \"customer.last_name\": \"Sharma\", \"$project\": [\"application_id\", \"customer.phone\"]}\n"
        f"{error_feedback}"
    )

    fallback_model = ChatOllama(model="llama3.1:8b", temperature=0.0, format="json")
    raw_completion_prompt = (
        "<|system|>\n"
        f"{system_instructions}\n"
        "<|end|>\n"
        "<|user|>\n"
        f"Query: {state['user_query']}\n"
        "<|end|>\n"
        "<|assistant|>\n"
    )
    ai_response = fallback_model.invoke(raw_completion_prompt)
    content = ai_response.content.strip()
    return {"shadow_query_str": content}

def executor_node(state: AgentState) -> Dict[str, Any]:
    print("Node 3: Executing Query Against MongoDB...")
    current_retry = state.get("retry_count", 0)
    try:
        raw_str = state["shadow_query_str"]
        if "```" in raw_str:
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_str, re.DOTALL)
            if match:
                raw_str = match.group(1)
        match_json = re.search(r'(\{.*\})', raw_str, re.DOTALL)
        if match_json:
            raw_str = match_json.group(1)
        raw_str = raw_str.strip()
        print(f"DEBUG: LLM translated output string: {raw_str}")
        query_dict = json.loads(raw_str)

        if isinstance(query_dict, dict) and "error" in query_dict:
            raise ValueError(query_dict["error"])

        project_fields = None
        is_count_query = False
        
        def extract_and_remove_special(d: Any) -> Any:
            nonlocal project_fields, is_count_query
            if isinstance(d, dict):
                if "$project" in d:
                    project_fields = d["$project"]
                    d = {k: v for k, v in d.items() if k != "$project"}
                if "$count" in d:
                    if d["$count"] is True or str(d["$count"]).lower() == "true":
                        is_count_query = True
                    d = {k: v for k, v in d.items() if k != "$count"}
                return {k: extract_and_remove_special(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [extract_and_remove_special(item) for item in d]
            return d

        query_dict = extract_and_remove_special(query_dict)

        is_aggregation = isinstance(query_dict, list) or (isinstance(query_dict, dict) and "$group" in query_dict)
        if is_aggregation:
            pipeline = query_dict if isinstance(query_dict, list) else [{"$group": query_dict["$group"]}]
            print(f"Running Aggregate Pipeline: {json.dumps(pipeline)}")
            records = list(db_collection.aggregate(pipeline))
            return {
                "mongo_query_dict": pipeline,
                "database_results": records,
                "project_fields": None,
                "is_count_query": False,
                "error_message": ""
            }

        filter_criteria = {}
        sort_criteria = {}
        limit_val = None

        if isinstance(query_dict, dict):
            if "$query" in query_dict:
                filter_criteria = query_dict["$query"]
                if "$sort" in query_dict:
                    sort_criteria = query_dict["$sort"]
                if "$limit" in query_dict:
                    limit_val = query_dict["$limit"]
            else:
                for k, v in query_dict.items():
                    if k == "$sort":
                        sort_criteria = v
                    elif k == "$limit":
                        limit_val = v
                    else:
                        filter_criteria[k] = v

        print(f"Running Find Filter: {json.dumps(filter_criteria)} | Sort: {sort_criteria} | Limit: {limit_val}")
        cursor = db_collection.find(filter_criteria)
        if sort_criteria:
            cursor = cursor.sort(list(sort_criteria.items()))
        if limit_val is not None:
            cursor = cursor.limit(int(limit_val))
            
        records = list(cursor)
        return {
            "mongo_query_dict": filter_criteria,
            "database_results": records,
            "project_fields": project_fields,
            "is_count_query": is_count_query,
            "error_message": ""
        }
    except Exception as err:
        return {"error_message": str(err), "retry_count": current_retry + 1}

def presentation_node(state: AgentState) -> Dict[str, Any]:
    print("Node 4: Presentation Node - Rendering ASCII Table...")
    db_results = state.get("database_results")
    is_count_query = state.get("is_count_query", False)
    error_msg = state.get("error_message")
    project_fields = state.get("project_fields")

    if error_msg:
        if "unrelated_query" in error_msg:
            body_content = "Query is not related to any database schema properties or records."
        else:
            body_content = f"Error executing query: {error_msg}"
    elif is_count_query:
        body_content = f"TOTAL COUNT: {len(db_results) if db_results else 0}"
    elif not db_results:
        body_content = "No matching records found."
    else:
        flat_docs = []
        for doc in db_results:
            doc_copy = dict(doc)
            doc_copy.pop("_id", None)
            flat = flatten_dict(doc_copy)
            
            if project_fields:
                filtered_flat = {}
                for pk in project_fields:
                    pk_flat = pk.replace(".", " -> ")
                    if pk_flat in flat:
                        filtered_flat[pk_flat] = flat[pk_flat]
                    else:
                        for k, v in flat.items():
                            if k == pk_flat or k.startswith(pk_flat + " -> "):
                                filtered_flat[k] = v
                flat_docs.append(filtered_flat if filtered_flat else flat)
            else:
                flat_docs.append(flat)

        body_content = render_ascii_table(flat_docs)

    return {"final_output_text": body_content}

def route_execution_feedback(state: AgentState):
    if state.get("error_message") and state["retry_count"] < 2:
        return "try_self_healing_loop"
    return "continue_to_formatting"

workflow = StateGraph(AgentState)
workflow.add_node("extract_schema", schema_extractor_node)
workflow.add_node("compile_query", translator_node)
workflow.add_node("run_database_query", executor_node)
workflow.add_node("generate_response", presentation_node)

workflow.set_entry_point("extract_schema")
workflow.add_edge("extract_schema", "compile_query")
workflow.add_edge("compile_query", "run_database_query")
workflow.add_conditional_edges(
    "run_database_query",
    route_execution_feedback,
    {
        "try_self_healing_loop": "compile_query",
        "continue_to_formatting": "generate_response"
    }
)
workflow.add_edge("generate_response", END)
compiled_agent_graph = workflow.compile()

if __name__ == "__main__":
    print("\n=======================================================")
    print("Local SLM Database CLI Gateway Initiated.")
    print("Using ONLY local Ollama (llama3.1:8b). Security bypassed.")
    print("Type 'exit' to quit.\n=======================================================\n")
    
    while True:
        user_prompt = input("Enter Query: ").strip()
        if user_prompt.lower() == 'exit':
            print("Goodbye!")
            break
        if not user_prompt:
            continue
            
        initial_state = {
            "user_query": user_prompt,
            "retry_count": 0,
            "error_message": ""
        }
        
        final_state = compiled_agent_graph.invoke(initial_state)
        print(f"\n[QUERY RESPONSE]:\n{final_state['final_output_text']}\n")
        print("-" * 60)
