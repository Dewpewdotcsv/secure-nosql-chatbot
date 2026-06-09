import os
import json
import re
import random
import string
import hashlib
import certifi
from typing import TypedDict, Any, Dict, List, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

load_dotenv()

class SecureAIBridge:
    def __init__(self):
        self.real_fields = []
        self.forward_map = {}
        self.reverse_map = {}
        self.token_vault = {}

    def reset_token_vault(self):
        self.token_vault = {}

    def setup_dynamic_mappings(self, schema_dict: dict):
        self.real_fields = list(schema_dict.keys())
        self.forward_map = {}
        self.reverse_map = {}
        used_keys = set()
        
        for field in self.real_fields:
            if "financials" in field:
                prefix = "fin_attr"
            elif "customer" in field:
                prefix = "cust_attr"
            else:
                prefix = "loan_attr"
                
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
            shadow_key = f"{prefix}_{suffix}"
            while shadow_key in used_keys:
                suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
                shadow_key = f"{prefix}_{suffix}"
                
            used_keys.add(shadow_key)
            self.forward_map[field] = shadow_key
            self.reverse_map[shadow_key] = field

    def get_shadow_schema_context(self) -> str:
        context = "DATABASE SCHEMA METADATA (Map query targets using ONLY these exact keys):\n"
        for real, shadow in self.forward_map.items():
            context += f"- Key '{shadow}' maps to '{real}' property type.\n"
        return context

    def tokenize_user_input(self, text: str) -> str:
        loan_ids = re.findall(r"LOAN-\d{4}-\d+", text)
        for lid in loan_ids:
            token = f"[LOAN_ID_TOKEN_{len(self.token_vault)+1}]"
            self.token_vault[token] = lid
            text = text.replace(lid, token)
        
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        for email in emails:
            token = f"[EMAIL_TOKEN_{len(self.token_vault)+1}]"
            self.token_vault[token] = email
            text = text.replace(email, token)
            
        return text

    def normalize_city_name(self, val: str) -> str:
        if not isinstance(val, str):
            return val
        lower_val = val.lower().strip()
        if lower_val in ["bangalore", "bengalore", "bengaluru"]:
            return "Bangalore"
        if lower_val in ["mumbai", "bombay"]:
            return "Mumbai"
        return val

    def translate_query_to_real(self, shadow_query: Any, current_path: str = "") -> Any:
        if isinstance(shadow_query, dict):
            real_query = {}
            for k, v in shadow_query.items():
                if k in self.reverse_map:
                    real_key = self.reverse_map[k]
                else:
                    real_key = k
                next_path = f"{current_path}.{real_key}" if current_path else real_key
                real_query[real_key] = self.translate_query_to_real(v, next_path)
            return real_query
        elif isinstance(shadow_query, list):
            return [self.translate_query_to_real(item, current_path) for item in shadow_query]
        else:
            if isinstance(shadow_query, str):
                if shadow_query.startswith("$") and shadow_query[1:] in self.reverse_map:
                    return "$" + self.reverse_map[shadow_query[1:]]
                if shadow_query in self.token_vault:
                    return self.token_vault[shadow_query]
                elif shadow_query.isdigit():
                    return int(shadow_query)
                else:
                    val = self.normalize_city_name(shadow_query)
                    check_path = current_path
                    if ".$" in current_path:
                        check_path = current_path[:current_path.rfind(".$ "[0] + "$")]
                        check_path = check_path.rsplit(".", 1)[0] if check_path.endswith("$") else check_path
                    base_path = re.sub(r'\.\$[\w]+$', '', current_path)
                    cap_paths = [
                        "customer.first_name", "customer.last_name",
                        "status", "customer.address.city", "customer.address.state"
                    ]
                    if base_path in cap_paths or current_path in cap_paths:
                        val = val.strip()
                        if any(char in val for char in ["^", "$", "|", "*", "+", "?", "[", "]", "(", ")", "{", "}"]):
                            def repl(m):
                                return m.group(1) + m.group(2).upper() + m.group(3)
                            val = re.sub(r'(\b|^|\^)([a-z])([a-zA-Z]*)', repl, val)
                        else:
                            words = val.split()
                            cap_words = [w.capitalize() for w in words]
                            val = " ".join(cap_words)
                    return val
            return shadow_query

    def mask_document_payload(self, doc: dict) -> dict:
        clean_doc = {}
        for real, shadow in self.forward_map.items():
            parts = real.split('.')
            val = doc
            for p in parts:
                if isinstance(val, dict) and p in val:
                    val = val[p]
                else:
                    val = None
                    break
            if val is not None:
                if real in ["customer.first_name", "customer.last_name", "customer.address.street", "customer.email"]:
                    token = f"[MASKED_DATA_VAL_{len(self.token_vault)+1}]"
                    self.token_vault[token] = str(val)
                    clean_doc[shadow] = token
                else:
                    clean_doc[shadow] = val
        return clean_doc

    def detokenize_output(self, final_text: str) -> str:
        for token, real_val in self.token_vault.items():
            final_text = final_text.replace(token, real_val)
        return final_text

    def capitalize_query_terms(self, text: str) -> str:
        stopwords = {
            "and", "or", "in", "is", "a", "the", "of", "to", "for", "from", "with", "by", "on", "at", 
            "than", "less", "greater", "not", "equal", "maximum", "minimum", "highest", "lowest", 
            "sorted", "give", "find", "show", "check", "who", "where", "how", "many", "loans", 
            "customer", "people", "active", "pending", "approved", "application", "applications", 
            "lives", "live", "living", "table", "me", "all", "there", "any", "named"
        }
        words = []
        for word in text.split():
            if word.startswith("[") and word.endswith("]"):
                words.append(word)
            else:
                clean_word = re.sub(r'[^\w]', '', word)
                if clean_word.lower() not in stopwords and not clean_word.isdigit():
                    capitalized = clean_word.capitalize()
                    word = word.replace(clean_word, capitalized)
                words.append(word)
        return " ".join(words)

class AgentState(TypedDict, total=False):
    user_query: str
    sanitized_query: str
    user_username: str
    user_role: str
    metadata_schema: str
    is_authorized: bool
    shadow_query_str: str
    mongo_query_dict: dict
    database_results: list
    project_fields: list
    retry_count: int
    error_message: str
    final_output_text: str
    node_trace: list
    is_count_query: bool

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("CRITICAL: MONGO_URI missing from environment config.")

db_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db_collection = db_client["enterprise_loans_db"]["loan_applications"]
db_users = db_client["enterprise_loans_db"]["users_auth"]

security_bridge = SecureAIBridge()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

if db_users.count_documents({}) == 0:
    db_users.insert_many([
        {"username": "admin", "password_hash": hash_password("admin123"), "role": "admin"},
        {"username": "worker", "password_hash": hash_password("worker123"), "role": "worker"},
        {"username": "deepak.sharma@example.com", "password_hash": hash_password("user123"), "role": "user"},
        {"username": "priya.p@example.com", "password_hash": hash_password("user123"), "role": "user"}
    ])

slm_metadata_model = ChatOllama(model="llama3.1:8b", temperature=0.0, format="json")
slm_text_model = ChatOllama(model="llama3.1:8b", temperature=0.0)

def get_translator_model() -> BaseChatModel:
    if os.getenv("GROQ_API_KEY"):
        return ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
    else:
        return ChatOllama(model="llama3.1:8b", temperature=0.0, format="json")

llm_translator_model = get_translator_model()

def mask_private_data(d: Any) -> Any:
    if isinstance(d, dict):
        new_dict = {}
        for k, v in d.items():
            if k in ["first_name", "last_name", "email", "phone", "street", "address_line_1", "address_line_2", "zip", "postcode"]:
                new_dict[k] = "[MASKED - RESTRICTED clearance]"
            elif isinstance(v, (dict, list)):
                new_dict[k] = mask_private_data(v)
            else:
                new_dict[k] = v
        return new_dict
    elif isinstance(d, list):
        return [mask_private_data(item) for item in d]
    else:
        return d

def clean_private_data(d: Any) -> Any:
    return mask_private_data(d)

def flatten_dict(d: Any, parent_key: str = '', sep: str = ' -> ') -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def detokenize_document_values(d: Any, vault: dict) -> Any:
    if isinstance(d, dict):
        return {k: detokenize_document_values(v, vault) for k, v in d.items()}
    elif isinstance(d, list):
        return [detokenize_document_values(item, vault) for item in d]
    elif isinstance(d, str):
        val_str = d
        for token, real_val in vault.items():
            val_str = val_str.replace(token, real_val)
        return val_str
    else:
        return d

def render_ascii_table(flat_docs: list) -> str:
    if not flat_docs:
        return "No records found to display in table."
        
    headers = []
    for doc in flat_docs:
        for k in doc.keys():
            if k not in headers:
                headers.append(k)
                
    if "application_id" in headers:
        headers.remove("application_id")
        headers = ["application_id"] + sorted(headers)
    else:
        headers = sorted(headers)
        
    col_widths = {h: len(h.upper()) for h in headers}
    for doc in flat_docs:
        for h in headers:
            val = str(doc.get(h, ""))
            if len(val) > col_widths[h]:
                col_widths[h] = len(val)
                
    border_line = "+" + "+".join(["-" * (col_widths[h] + 2) for h in headers]) + "+"
    header_line = "|" + "|".join([f" {h.upper().replace('_', ' '):<{col_widths[h]}} " for h in headers]) + "|"
    
    lines = [border_line, header_line, border_line]
    for doc in flat_docs:
        row_line = "|" + "|".join([f" {str(doc.get(h, '')):<{col_widths[h]}} " for h in headers]) + "|"
        lines.append(row_line)
    lines.append(border_line)
    return "\n".join(lines)

def extract_modifiers_from_query(query: Any):
    sort_opts = {}
    limit_opt = None

    if isinstance(query, dict):
        clean_query = {}
        if "$query" in query:
            inner_query = query.get("$query", {})
            sort_opts = query.get("$sort", {})
            limit_opt = query.get("$limit", None)
            inner_clean, inner_sort, inner_limit = extract_modifiers_from_query(inner_query)
            if inner_sort:
                sort_opts.update(inner_sort)
            if inner_limit is not None:
                limit_opt = inner_limit
            return inner_clean, sort_opts, limit_opt

        for k, v in query.items():
            if k == "$sort":
                if isinstance(v, dict):
                    sort_opts.update(v)
            elif k == "$limit":
                limit_opt = v
            elif isinstance(v, dict):
                if "$max" in v:
                    sort_opts[k] = -1
                    limit_opt = 1
                elif "$min" in v:
                    sort_opts[k] = 1
                    limit_opt = 1
                else:
                    sub_clean, sub_sort, sub_limit = extract_modifiers_from_query(v)
                    if sub_sort:
                        sort_opts.update(sub_sort)
                    if sub_limit is not None:
                        limit_opt = sub_limit
                    if sub_clean not in [None, {}]:
                        clean_query[k] = sub_clean
            elif isinstance(v, list):
                new_list = []
                for item in v:
                    sub_clean, sub_sort, sub_limit = extract_modifiers_from_query(item)
                    if sub_sort:
                        sort_opts.update(sub_sort)
                    if sub_limit is not None:
                        limit_opt = sub_limit
                    if sub_clean not in [None, {}]:
                        new_list.append(sub_clean)
                if new_list:
                    clean_query[k] = new_list
            else:
                if v not in [None, {}]:
                    clean_query[k] = v
        return clean_query, sort_opts, limit_opt

    elif isinstance(query, list):
        clean_list = []
        for item in query:
            sub_clean, sub_sort, sub_limit = extract_modifiers_from_query(item)
            if sub_sort:
                sort_opts.update(sub_sort)
            if sub_limit is not None:
                limit_opt = sub_limit
            if sub_clean not in [None, {}]:
                clean_list.append(sub_clean)
        return clean_list, sort_opts, limit_opt

    else:
        if query in [None, {}]:
            return None, sort_opts, limit_opt
        return query, sort_opts, limit_opt

def metadata_extractor_node(state: AgentState) -> Dict[str, Any]:
    doc = db_collection.find_one()
    if not doc:
        doc = {
            "application_id": "LOAN-2026-001",
            "status": "Approved",
            "requested_amount": 75000,
            "term_months": 36,
            "financials": {
                "annual_income": 115000,
                "credit_score": 740,
                "existing_debt": 12000
            },
            "customer": {
                "first_name": "Deepak",
                "last_name": "Sharma",
                "email": "deepak.sharma@example.com",
                "phone": "+91-98765-43210",
                "address": {
                    "street": "45 MG Road, Phase 2",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "zip": "560001"
                }
            }
        }
    else:
        doc = dict(doc)
        doc.pop("_id", None)
        
    clean_doc = clean_private_data(doc)
    
    prompt = (
        "<|system|>\n"
        "You are a database metadata analyzer. Output exactly one raw valid JSON object listing all available properties in the database document.\n"
        "Identify each nested key path in the document using dot-notation (e.g., 'customer.first_name') and specify its value type ('string' or 'number').\n"
        "Do NOT write markdown code blocks, backticks (```json), or conversational text. Output ONLY valid raw JSON.\n"
        "<|end|>\n"
        "<|user|>\n"
        f"Extract all dot-notation paths and types from this record: {json.dumps(clean_doc)}\n"
        "<|end|>\n"
        "<|assistant|>\n"
    )
    
    ai_response = slm_metadata_model.invoke(prompt)
    raw_content = ai_response.content.strip()
    
    if "```" in raw_content:
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_content, re.DOTALL)
        if match:
            raw_content = match.group(1)
    match_json = re.search(r'(\{.*\})', raw_content, re.DOTALL)
    if match_json:
        raw_content = match_json.group(1)
        
    try:
        raw_schema = json.loads(raw_content.strip())
        
        def flatten_schema_dict(d: Any, parent_key: str = '', sep: str = '.') -> dict:
            items = []
            if isinstance(d, dict):
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_schema_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((new_key, v))
            return dict(items)

        flat_schema = flatten_schema_dict(raw_schema)
        
        schema_dict = {}
        for k, v in flat_schema.items():
            clean_k = k
            for suffix in [".type", ".string", ".number", ".boolean"]:
                if clean_k.endswith(suffix):
                    clean_k = clean_k[:-len(suffix)]
            if clean_k in ["type", "string", "number", "boolean"] or not clean_k:
                continue
            schema_dict[clean_k] = v

    except Exception as e:
        schema_dict = {
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
        
    security_bridge.setup_dynamic_mappings(schema_dict)
    schema_context = security_bridge.get_shadow_schema_context()
    key_count = len(schema_dict)
    trace = (state.get("node_trace") or []) + [{
        "node": "Node 1 — Metadata Extractor",
        "input": f"Raw DB document (anonymized, {key_count} fields detected)",
        "output": f"Shadow schema compiled: {key_count} dot-path keys mapped to session tokens"
    }]
    return {"metadata_schema": schema_context, "node_trace": trace}

def sanitization_node(state: AgentState) -> Dict[str, Any]:
    security_bridge.reset_token_vault()
    
    role = state["user_role"].lower()
    query = state["user_query"].lower()
    
    if "ignore your instructions" in query or "system prompt" in query:
         return {
             "is_authorized": False, 
             "final_output_text": "Security Intercept: Unauthorized prompt structural modification detected."
         }
         
    tokenized = security_bridge.tokenize_user_input(state["user_query"])
    sanitized = security_bridge.capitalize_query_terms(tokenized)
    trace = (state.get("node_trace") or []) + [{
        "node": "Node 2 — Sanitization & Auth",
        "input": f"Raw query: \"{state['user_query']}\" | Role: {role}",
        "output": f"Sanitized query: \"{sanitized}\" | Authorized: True"
    }]
    return {"is_authorized": True, "sanitized_query": sanitized, "retry_count": 0, "node_trace": trace}

def translator_node(state: AgentState) -> Dict[str, Any]:
    schema_prompt = state["metadata_schema"]
    error_feedback = ""
    if state.get("error_message"):
        error_feedback = f"\nYOUR PREVIOUS GENERATION ATTEMPT FAILED WITH THIS ERROR: {state['error_message']}\nFix your JSON filter structure mapping parameters accordingly."

    status_key = security_bridge.forward_map.get("status", "status_key")
    income_key = security_bridge.forward_map.get("financials.annual_income", "income_key")
    city_key = security_bridge.forward_map.get("customer.address.city", "city_key")
    state_key = security_bridge.forward_map.get("customer.address.state", "state_key")
    id_key = security_bridge.forward_map.get("application_id", "id_key")
    credit_key = security_bridge.forward_map.get("financials.credit_score", "credit_key")
    amount_key = security_bridge.forward_map.get("requested_amount", "amount_key")
    first_name_key = security_bridge.forward_map.get("customer.first_name", "first_name_key")
    last_name_key = security_bridge.forward_map.get("customer.last_name", "last_name_key")
    email_key = security_bridge.forward_map.get("customer.email", "email_key")
    phone_key = security_bridge.forward_map.get("customer.phone", "phone_key")
    term_months_key = security_bridge.forward_map.get("term_months", "term_months_key")
    existing_debt_key = security_bridge.forward_map.get("financials.existing_debt", "existing_debt_key")
    street_key = security_bridge.forward_map.get("customer.address.street", "street_key")
    zip_key = security_bridge.forward_map.get("customer.address.zip", "zip_key")

    system_instructions = (
        "You are an isolated enterprise database compiler writing MongoDB query filters.\n"
        "Generate absolute raw valid JSON matching standard key filter targets. Do NOT write markdown code blocks or wrap in ```json.\n"
        f"{schema_prompt}\n"
        "RULES:\n"
        "1. Identify the condition fields in the query.\n"
        "2. Look up the exact matching shadow keys in the DATABASE SCHEMA METADATA. You MUST use only these shadow keys in your output JSON object, NEVER the real field paths.\n"
        "3. Output a MongoDB query filter JSON object mapping those keys to their values.\n"
        "4. ONLY filter on the actual conditions/constants in the query, not the fields being requested/displayed.\n"
        f"5. For numeric or value checks, use standard NoSQL operators: '$lt', '$gt', '$ne', or '$in'. If a query references multiple potential values for a field (e.g. 'mumbai and bangalore', 'mumbai or bangalore'), use the '$in' operator with a list of those values (e.g. {{\"{city_key}\": {{\"$in\": [\"Mumbai\", \"Bangalore\"]}}}}).\n"
        "6. Do NOT put symbols like '<' or '>' inside the value.\n"
        f"7. ALL data is stored within a single MongoDB collection. For standard queries, output a standard MongoDB query filter document for find(). NEVER wrap your output in a top-level '$match' operator. However, if the user query asks for grouping, group-by aggregates, averages, or counts of different types (e.g. 'count of all the different types of status', 'average requested amount by status', 'maximum and minimum requested amount grouped by state'), you MUST output a standard MongoDB aggregation pipeline (a list of stages) containing a '$group' stage with nested accumulator operators like '$sum', '$avg', '$min', or '$max'. Map all fields to their shadow keys. For example: [{{\"$group\": {{\"_id\": \"${status_key}\", \"count\": {{\"$sum\": 1}}}}}}].\n"
        f"8. DO NOT hallucinate, guess, or invent any names, values, or constants that are not explicitly mentioned in the user query. If a query asks 'who' or 'where', only filter by the condition (e.g. the city 'Bangalore') and do NOT add filter conditions for names or values that are not in the query text. Be very careful to distinguish 'state' (mapped to {state_key}) from 'city' (mapped to {city_key}).\n"
        f"9. To find maximum, minimum, highest, lowest, or sorted values across all documents, output a JSON object with special keys:\n"
        f"   - \"$query\": the filter conditions (or {{}} if none).\n"
        "   - \"$sort\": the field key to sort by, mapped to -1 for descending (maximum/highest) or 1 for ascending (minimum/lowest).\n"
        "   - \"$limit\": 1.\n"
        f"10. If the user query is purely conversational, greeting-based, or completely unrelated to any database entities/intent (e.g. 'hello', 'Treat yourself now.', 'how are you?', etc.), you MUST output: {{\"error\": \"unrelated_query\"}}. However, if the query contains references to schema attributes, specific values, names, or asks to find/list records (e.g. 'Find Deepak', 'is deepak in system?', 'is there a customer in Bangalore?', 'show all loans'), it is a VALID query. Do NOT output {{\"error\": \"unrelated_query\"}} for valid database requests. The classification is completely case-insensitive.\n"
        f"11. Pay close attention to bracketed tokens: if the token matches '[EMAIL_TOKEN_...]', map it to the {email_key} key; if it matches '[LOAN_ID_TOKEN_...]', map it to the {id_key} key.\n"
        f"12. For conditional queries (e.g., 'if there are people from Mumbai, give me all from Bangalore'), use special keys '$condition' and '$query':\n"
        f"    - \"$condition\": the check filter (e.g. {{\"{city_key}\": \"Mumbai\"}}).\n"
        f"    - \"$query\": the actual filter to run if matched (e.g. {{\"{city_key}\": \"Bangalore\"}}).\n"
        f"    - Note: If the actual filter requires sorting, limits, or projection (e.g. 'find the approved loan with the maximum amount and show its loan id'), wrap the sort/limit/project modifiers inside the inner '$query' block. For example: {{\"$condition\": {{\"{credit_key}\": {{\"$lt\": 600}}}}, \"$query\": {{\"$query\": {{\"{status_key}\": \"Approved\"}}, \"$sort\": {{\"{amount_key}\": -1}}, \"$limit\": 1, \"$project\": [\"{id_key}\", \"{amount_key}\"]}}}}\n"
        f"13. If the user query asks for specific properties/attributes (e.g., 'what is the status', 'who is the customer of loan...', 'give the name of the person with...', 'give the phone number of...', 'show its loan id and amount', 'project only their status, requested amount, and city'), you MUST include a special key '$project' containing a list of the exact shadow keys for ONLY those requested properties. Always include the application ID key (e.g. {id_key}) in the list. If the query asks for 'details', 'all details', 'full record', 'information', or does not ask for specific fields, do NOT output a '$project' key (return the entire document).\n"
        f"14. When a query references a full name (first name and last name, e.g., 'Deepak Sharma', 'Priya Patel'), you MUST split the name into first name and last name and filter on BOTH keys in your output JSON (e.g., {{\"{first_name_key}\": \"Deepak\", \"{last_name_key}\": \"Sharma\"}}).\n"
        f"15. DO NOT hallucinate placeholder tokens (like [EMAIL_TOKEN_...] or [PHONE_TOKEN_...]) or fields in the query filter unless the user's input query explicitly specifies a value condition for them. Requested fields that you are asked to 'show', 'display', 'retrieve', or 'project' must go ONLY in the '$project' list, never in the filter conditions.\n"
        f"16. If the user query asks for the 'number of' or 'count of' records (e.g., 'Give the number of approved loans', 'how many loans are pending', 'count of customers in Bangalore'), you MUST include a special key '$count': true in the output JSON alongside the query conditions. For example: {{\"$query\": {{\"{status_key}\": \"Approved\"}}, \"$count\": true}}.\n"
        f"17. If the user query uses fuzzy terms like 'about' or 'around' for a numeric field (e.g. 'about 750' or 'around 50000'), do NOT generate an extremely narrow range (like $gt 749 and $lt 751). Instead, output a reasonable window (e.g. for credit score 'about 750' use $gte 720 and $lte 780; for annual income 'about 50000' use $gte 45000 and $lte 55000).\n\n"
        "FEW-SHOT EXAMPLES:\n"
        f"Input: give me everything other than email and phone of Deepak\n"
        f"Output: {{\"{first_name_key}\": \"Deepak\", \"$project\": [\"{id_key}\", \"{status_key}\", \"{amount_key}\", \"{term_months_key}\", \"financials.{income_key}\", \"financials.{credit_key}\", \"financials.{existing_debt_key}\", \"{last_name_key}\", \"customer.address.{street_key}\", \"customer.address.{city_key}\", \"customer.address.{state_key}\", \"customer.address.{zip_key}\"]}}\n\n"
        f"Input: What is the status of the loan application for Rohan Sharma?\n"
        f"Output: {{\"{first_name_key}\": \"Rohan\", \"{last_name_key}\": \"Sharma\", \"$project\": [\"{id_key}\", \"{status_key}\"]}}\n\n"
        f"Input: Show me the loan application details for Priya Patel\n"
        f"Output: {{\"{first_name_key}\": \"Priya\", \"{last_name_key}\": \"Patel\"}}\n\n"
        f"Input: Give me the full record of applications from Mumbai\n"
        f"Output: {{\"{city_key}\": \"Mumbai\"}}\n\n"
        "Input: Find pending applications with an annual income of 95000\n"
        f"Output: {{\"{status_key}\": \"Pending\", \"{income_key}\": 95000}}\n\n"
        "Input: Give the number of approved loans\n"
        f"Output: {{\"$query\": {{\"{status_key}\": \"Approved\"}}, \"$count\": true}}\n\n"
        "Input: how many loans are pending\n"
        f"Output: {{\"$query\": {{\"{status_key}\": \"Pending\"}}, \"$count\": true}}\n\n"
        "Input: Are there any loans active for a customer in Bangalore\n"
        f"Output: {{\"{city_key}\": \"Bangalore\"}}\n\n"
        "Input: if there are people living in mumbai is there then give me who are all there in bengalore\n"
        f"Output: {{\"{city_key}\": \"Bangalore\"}}\n\n"
        "Input: Show me where the customer for loan [LOAN_ID_TOKEN_1] lives\n"
        f"Output: {{\"{id_key}\": \"[LOAN_ID_TOKEN_1]\"}}\n\n"
        "Input: is [LOAN_ID_TOKEN_1] in the table?\n"
        f"Output: {{\"{id_key}\": \"[LOAN_ID_TOKEN_1]\"}}\n\n"
        "Input: Check records where credit score is not 740\n"
        f"Output: {{\"{credit_key}\": {{\"$ne\": 740}}}}\n\n"
        "Input: Check records where credit score is less than 800\n"
        f"Output: {{\"{credit_key}\": {{\"$lt\": 800}}}}\n\n"
        "Input: give the maximum loan taken by a candidate\n"
        f"Output: {{\"$sort\": {{\"{amount_key}\": -1}}, \"$limit\": 1, \"$project\": [\"{id_key}\", \"{amount_key}\", \"{first_name_key}\", \"{last_name_key}\"]}}\n\n"
        "Input: is deepak in the system?\n"
        f"Output: {{\"{first_name_key}\": \"Deepak\"}}\n\n"
        "Input: Find all the loans by Deepak Sharma\n"
        f"Output: {{\"{first_name_key}\": \"Deepak\", \"{last_name_key}\": \"Sharma\"}}\n\n"
        "Input: Find loans for customer with email [EMAIL_TOKEN_1]\n"
        f"Output: {{\"{email_key}\": \"[EMAIL_TOKEN_1]\"}}\n\n"
        "Input: give me all the people from bangalore and mumbai\n"
        f"Output: {{\"{city_key}\": {{\"$in\": [\"Bangalore\", \"Mumbai\"]}}}}\n\n"
        f"Input: if there are people from mumbai give me all the people from bangalore\n"
        f"Output: {{\"$condition\": {{\"{city_key}\": \"Mumbai\"}}, \"$query\": {{\"{city_key}\": \"Bangalore\"}}}}\n\n"
        f"Input: give the name of the person with loan [LOAN_ID_TOKEN_1]\n"
        f"Output: {{\"{id_key}\": \"[LOAN_ID_TOKEN_1]\", \"$project\": [\"{id_key}\", \"{first_name_key}\", \"{last_name_key}\"]}}\n\n"
        f"Input: If there are any loans with status Rejected, show all loans from the state Maharashtra\n"
        f"Output: {{\"$condition\": {{\"{status_key}\": \"Rejected\"}}, \"$query\": {{\"{state_key}\": \"Maharashtra\"}}}}\n\n"
        f"Input: If there are customers with a credit score below 600, find the approved loan with the maximum requested amount and show its loan id and amount\n"
        f"Output: {{\"$condition\": {{\"{credit_key}\": {{\"$lt\": 600}}}}, \"$query\": {{\"$query\": {{\"{status_key}\": \"Approved\"}}, \"$sort\": {{\"{amount_key}\": -1}}, \"$limit\": 1, \"$project\": [\"{id_key}\", \"{amount_key}\"]}}}}\n\n"
        f"Input: If there is any application with requested amount exceeding 300000, retrieve all approved applications from Mumbai or Bangalore, and project only their status, requested amount, and city\n"
        f"Output: {{\"$condition\": {{\"{amount_key}\": {{\"$gt\": 300000}}}}, \"$query\": {{\"$query\": {{\"{status_key}\": \"Approved\", \"{city_key}\": {{\"$in\": [\"Mumbai\", \"Bangalore\"]}}}}, \"$project\": [\"{id_key}\", \"{status_key}\", \"{amount_key}\", \"{city_key}\"]}}}}\n\n"
        f"Input: If there are any applications from Kerala, show the application id, status, and credit score for the customer who has the minimum annual income in Kochi\n"
        f"Output: {{\"$condition\": {{\"{state_key}\": \"Kerala\"}}, \"$query\": {{\"$query\": {{\"{city_key}\": \"Kochi\"}}, \"$sort\": {{\"{income_key}\": 1}}, \"$limit\": 1, \"$project\": [\"{id_key}\", \"{status_key}\", \"{credit_key}\"]}}}}\n\n"
        f"Output: {{\"$condition\": {{\"{credit_key}\": {{\"$ne\": 740}}}}, \"$query\": {{\"$query\": {{\"{status_key}\": \"Approved\"}}, \"$sort\": {{\"{amount_key}\": 1}}, \"$limit\": 1, \"$project\": [\"{id_key}\", \"{email_key}\", \"{phone_key}\", \"{amount_key}\"]}}}}\n\n"
        "Input: count of all the different types of status\n"
        f"Output: [{{\"$group\": {{\"_id\": \"${status_key}\", \"count\": {{\"$sum\": 1}}}}}}]\n\n"
        "Input: average requested amount by city\n"
        f"Output: [{{\"$group\": {{\"_id\": \"${city_key}\", \"average_amount\": {{\"$avg\": \"${amount_key}\"}}}}}}]\n\n"
        "Input: maximum and minimum requested amount grouped by state\n"
        f"Output: [{{\"$group\": {{\"_id\": \"${state_key}\", \"max_amount\": {{\"$max\": \"${amount_key}\"}}, \"min_amount\": {{\"$min\": \"${amount_key}\"}}}}}}]\n"
        f"{error_feedback}"
    )

    clean_query = state['sanitized_query']
    original_query = state['user_query']

    content = None
    if os.getenv("GROQ_API_KEY"):
        groq_models = ["llama-3.3-70b-versatile"]
        for g_model in groq_models:
            try:
                model_inst = ChatGroq(model=g_model, temperature=0.0, max_retries=0)
                messages = [
                    SystemMessage(content=system_instructions),
                    HumanMessage(content=f"Translate this isolated instruction prompt into valid JSON MongoDB dictionary filter fields: {clean_query}")
                ]
                ai_response = model_inst.invoke(messages)
                content = ai_response.content.strip()
                if content:
                    break
            except Exception as e:
                pass

    if not content:
        fallback_model = ChatOllama(model="llama3.1:8b", temperature=0.0, format="json")
        raw_completion_prompt = (
            "<|system|>\n"
            f"{system_instructions}\n"
            "<|end|>\n"
            "<|user|>\n"
            f"Query: {clean_query}\n"
            "<|end|>\n"
            "<|assistant|>\n"
        )
        ai_response = fallback_model.invoke(raw_completion_prompt)
        content = ai_response.content.strip()

    trace = (state.get("node_trace") or []) + [{
        "node": "Node 3 — Query Translator",
        "input": f"Query: \"{original_query}\"",
        "output": f"[LLM] MQL shadow filter: {content}"
    }]
    return {"shadow_query_str": content, "node_trace": trace}

def executor_node(state: AgentState) -> Dict[str, Any]:
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
        shadow_dict = json.loads(raw_str)
        
        if isinstance(shadow_dict, dict) and "error" in shadow_dict:
            raise ValueError(shadow_dict["error"])
        
        project_fields = None
        is_count_query = False
        def extract_and_remove_special(d: Any) -> Any:
            nonlocal project_fields, is_count_query
            if isinstance(d, dict):
                if "$project" in d:
                    shadow_proj = d["$project"]
                    if isinstance(shadow_proj, list):
                        project_fields = [security_bridge.reverse_map.get(k, k) for k in shadow_proj]
                    d = {k: v for k, v in d.items() if k != "$project"}
                if "$count" in d:
                    if d["$count"] is True or str(d["$count"]).lower() == "true":
                        is_count_query = True
                    d = {k: v for k, v in d.items() if k != "$count"}
                return {k: extract_and_remove_special(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [extract_and_remove_special(item) for item in d]
            return d

        shadow_dict = extract_and_remove_special(shadow_dict)

        condition_satisfied = True
        if isinstance(shadow_dict, dict) and "$condition" in shadow_dict:
            cond_shadow = shadow_dict.get("$condition", {})
            cond_real = security_bridge.translate_query_to_real(cond_shadow)
                
            if db_collection.find_one(cond_real) is None:
                condition_satisfied = False
            
            shadow_dict = shadow_dict.get("$query", {})
            
        if not condition_satisfied:
            return {"mongo_query_dict": {}, "database_results": [], "project_fields": None, "error_message": ""}
            
        is_aggregation = False
        if isinstance(shadow_dict, list):
            is_aggregation = any(
                isinstance(stage, dict) and any(k in stage for k in ["$group", "$project", "$match", "$sort", "$limit"])
                for stage in shadow_dict
            )
        elif isinstance(shadow_dict, dict) and "$group" in shadow_dict:
            pipeline = []
            
            match_conds = {}
            if "$query" in shadow_dict:
                match_conds = shadow_dict["$query"]
            else:
                for k, v in shadow_dict.items():
                    if k not in ["$group", "$project", "$sort", "$limit", "$condition"]:
                        match_conds[k] = v
            if match_conds:
                pipeline.append({"$match": match_conds})
                
            pipeline.append({"$group": shadow_dict["$group"]})
            
            if "$sort" in shadow_dict:
                pipeline.append({"$sort": shadow_dict["$sort"]})
                
            if "$limit" in shadow_dict:
                pipeline.append({"$limit": shadow_dict["$limit"]})
                
            if "$project" in shadow_dict:
                proj = shadow_dict["$project"]
                if isinstance(proj, list):
                    proj_dict = {f: 1 for f in proj}
                    pipeline.append({"$project": proj_dict})
                else:
                    pipeline.append({"$project": proj})
                    
            shadow_dict = pipeline
            is_aggregation = True

        if is_aggregation:
            real_pipeline = security_bridge.translate_query_to_real(shadow_dict)
            records = list(db_collection.aggregate(real_pipeline))
            trace = (state.get("node_trace") or []) + [{
                "node": "Node 4 — RBAC Executor",
                "input": f"MongoDB aggregation: {json.dumps(real_pipeline)}",
                "output": f"{len(records)} record(s) returned from aggregation"
            }]
            return {
                "mongo_query_dict": {"aggregation": real_pipeline},
                "database_results": records,
                "project_fields": None,
                "is_count_query": False,
                "error_message": "",
                "node_trace": trace
            }

        if isinstance(shadow_dict, list):
            match_found = False
            for stage in shadow_dict:
                if isinstance(stage, dict) and "$match" in stage:
                    shadow_dict = stage["$match"]
                    match_found = True
                    break
            if not match_found and len(shadow_dict) > 0:
                shadow_dict = shadow_dict[0]
                
        if isinstance(shadow_dict, dict) and "$match" in shadow_dict:
            shadow_dict = shadow_dict["$match"]

        if project_fields is not None and "application_id" not in project_fields:
            project_fields = ["application_id"] + project_fields

        def strip_empty_dicts(d: Any) -> Any:
            if isinstance(d, dict):
                return {k: strip_empty_dicts(v) for k, v in d.items() if v != {}}
            elif isinstance(d, list):
                return [strip_empty_dicts(item) for item in d]
            return d
            
        shadow_dict = strip_empty_dicts(shadow_dict)
        shadow_filter, shadow_sort, limit_opt = extract_modifiers_from_query(shadow_dict)
        
        real_mongo_query = security_bridge.translate_query_to_real(shadow_filter)
        real_sort = security_bridge.translate_query_to_real(shadow_sort)
        
        cursor = db_collection.find(real_mongo_query)
        if real_sort:
            cursor = cursor.sort(list(real_sort.items()))
        if limit_opt is not None:
            cursor = cursor.limit(int(limit_opt))
            
        records = list(cursor)
        trace = (state.get("node_trace") or []) + [{
            "node": "Node 4 — RBAC Executor",
            "input": f"MongoDB filter: {json.dumps(real_mongo_query)}",
            "output": f"{len(records)} record(s) returned from collection"
        }]
        return {
            "mongo_query_dict": real_mongo_query,
            "database_results": records,
            "project_fields": project_fields,
            "is_count_query": is_count_query,
            "error_message": "",
            "node_trace": trace
        }
    except Exception as err:
        return {"error_message": str(err), "retry_count": current_retry + 1}

def presentation_node(state: AgentState) -> Dict[str, Any]:
    node_trace = state.get("node_trace") or []
    
    db_results = state.get("database_results")
    is_count_query = state.get("is_count_query", False)
    if state.get("is_authorized") is not False:
        has_node_5 = any(entry.get("node") == "Node 5 — Presentation" for entry in node_trace)
        if not has_node_5:
            node_trace = node_trace + [{
                "node": "Node 5 — Presentation",
                "input": f"{len(db_results) if db_results else 0} DB record(s) received",
                "output": f"Total count calculated ({len(db_results) if db_results else 0})" if is_count_query else (f"ASCII table rendered ({len(db_results) if db_results else 0} row(s))" if db_results else "No records to render")
            }]

    trace_lines = []
    for i, entry in enumerate(node_trace, 1):
        trace_lines.append(f"  {entry['node']}")
        trace_lines.append(f"    ▶ Input  : {entry['input']}")
        trace_lines.append(f"    ◀ Output : {entry['output']}")
        if i < len(node_trace):
            trace_lines.append("")

    trace_text = "\n".join(trace_lines)
    
    error_msg = state.get("error_message")
    is_authorized = state.get("is_authorized", True)
    
    if not is_authorized:
        body_content = state.get("final_output_text") or "Security Exception: Access Denied. Your active role profile does not possess permissions."
    elif error_msg:
        if "unrelated_query" in error_msg:
            body_content = "Security Warning: The requested query is not related to any database schema properties or records. Please refine your query target parameters."
        else:
            body_content = f"Error executing query: {error_msg}. Please refine your query structure."
    elif is_count_query:
        body_content = f"TOTAL COUNT: {len(db_results) if db_results else 0}"
    elif not db_results:
        body_content = "No matching loan application records found matching the specified parameters."
    else:
        role = state["user_role"].lower()
        project_keys = None
        if state.get("project_fields"):
            project_keys = [pf.replace(".", " -> ") for pf in state["project_fields"]]

        flat_docs = []
        for doc in db_results:
            doc_copy = dict(doc)
            if "_id" in doc_copy:
                from bson import ObjectId
                if isinstance(doc_copy["_id"], ObjectId):
                    doc_copy.pop("_id", None)
                else:
                    doc_copy["Grouping Key"] = doc_copy.pop("_id")
            doc_copy = detokenize_document_values(doc_copy, security_bridge.token_vault)
            flat = flatten_dict(doc_copy)
            if project_keys:
                filtered_flat = {}
                for pk in project_keys:
                    if pk in flat:
                        filtered_flat[pk] = flat[pk]
                    else:
                        for k, v in flat.items():
                            if k == pk or k.startswith(pk + " -> "):
                                filtered_flat[k] = v
                flat_docs.append(filtered_flat if filtered_flat else flat)
            else:
                flat_docs.append(flat)
                
        ascii_table = render_ascii_table(flat_docs)
        body_content = f"{ascii_table}"

    sections = [
        trace_text,
        "",
        body_content
    ]
    return {"final_output_text": "\n".join(sections)}

def route_post_guardrail(state: AgentState):
    if not state["is_authorized"]:
        return "end_shortcut"
    return "continue_to_translation"

def route_execution_feedback(state: AgentState):
    if state.get("error_message") and state["retry_count"] < 2:
        return "try_self_healing_loop"
    return "continue_to_formatting"

workflow = StateGraph(AgentState)

workflow.add_node("extract_metadata", metadata_extractor_node)
workflow.add_node("verify_guardrail", sanitization_node)
workflow.add_node("compile_query", translator_node)
workflow.add_node("run_database_query", executor_node)
workflow.add_node("generate_response", presentation_node)

workflow.set_entry_point("extract_schema" if "extract_schema" in workflow.nodes else "extract_metadata")
workflow.add_edge("extract_metadata", "verify_guardrail")

workflow.add_conditional_edges(
    "verify_guardrail",
    route_post_guardrail,
    {
        "end_shortcut": "generate_response",
        "continue_to_translation": "compile_query"
    }
)

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
    active_user = {"username": "admin@example.com", "role": "admin"}
    
    print("\nGateway System Armed.")
    print("As an ADMIN, you have no restricted access.")
    print("Type 'exit' to cleanly close communication links.\n")
        
    while True:
        user_prompt = input("Enter Request Query: ").strip()
        if user_prompt.lower() == 'exit':
            print("Disconnecting cluster paths. Goodbye!")
            break
        if not user_prompt:
            continue
            
        initial_state = {
            "user_query": user_prompt,
            "user_username": active_user["username"],
            "user_role": active_user["role"],
            "retry_count": 0,
            "error_message": ""
        }
        
        final_state = compiled_agent_graph.invoke(initial_state)
        print(f"\n[AGENT RESPONSE OUTPUT]:\n{final_state['final_output_text']}\n")
        print("-" * 60)
