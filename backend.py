import os
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app_enterprise import compiled_agent_graph, security_bridge

app = FastAPI(title="Secure DB Gateway API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    username: str
    role: str

class QueryResponse(BaseModel):
    response: str

@app.post("/api/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    try:
        security_bridge.reset_token_vault()
        
        initial_state = {
            "user_query": req.query,
            "user_username": req.username,
            "user_role": req.role,
            "retry_count": 0,
            "error_message": ""
        }
        
        final_state = compiled_agent_graph.invoke(initial_state)
        return {"response": final_state["final_output_text"]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)
