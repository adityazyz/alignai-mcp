from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any, List, Optional, Annotated
from typing_extensions import Annotated
from langgraph.graph.message import add_messages
from agents.data_fetching import data_fetching_node
from agents.transcription import transcription_node
from agents.analysis import analysis_node
from agents.summary_generation import summary_generation_node
from agents.storage_response import storage_response_node
from agents.parallel_coordinator import parallel_coordinator_node
from agents.performance_record import performance_records_node
from middleware import verify_auth_token
import asyncio
import json
from sse_starlette.sse import EventSourceResponse
import logging
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add middleware to verify auth token
app.middleware("http")(verify_auth_token)

class ProcessRequest(BaseModel):
    meeting_id: str
    # auth_token is now verified by middleware, but kept in model for compatibility
    auth_token: Optional[str] = None

class State(TypedDict):
    meetingId: str
    organizationId: str
    departmentId: Optional[str]
    botId: Optional[str]
    meeting_data: Optional[Dict[str, Any]]
    participants: List[Dict[str, str]]
    attendees: List[Dict[str, str]]
    attendees_events : Optional[List[Dict[str, Any]]]
    audioUrl: Optional[str]
    videoUrl: Optional[str]
    transcription: Optional[str]
    meetingSummary: Optional[Dict[str, Any]]
    tasks: Optional[List[Dict[str, Any]]]
    generatedContent: Optional[List[Dict[str, Any]]]
    messages: Annotated[List[str], add_messages]
    status: str
    auth_token: str
    initial_ids: Dict[str, Any]
    # Analysis flags
    generate_summary: Optional[bool]
    tasks_detected: Optional[bool]
    content_detected: Optional[bool]
    content_details: Optional[Dict[str, Any]]
    # Parallel processing results
    parallel_results: Optional[Dict[str, Any]]

def create_workflow():
    workflow = StateGraph(State)
    
    # Add all nodes
    workflow.add_node("data_fetching", data_fetching_node)
    workflow.add_node("transcription_processing", transcription_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("parallel_coordinator", parallel_coordinator_node)
    workflow.add_node("summary_generation", summary_generation_node)
    workflow.add_node("performance_records", performance_records_node)
    workflow.add_node("storage_response", storage_response_node)
    
    # Set entry point
    workflow.set_entry_point("data_fetching")
    
    # Create flow that includes summary_generation_node after parallel_coordinator
    workflow.add_edge("data_fetching", "transcription_processing")
    workflow.add_edge("transcription_processing", "analysis")
    workflow.add_edge("analysis", "parallel_coordinator")
    workflow.add_edge("parallel_coordinator", "summary_generation")
    workflow.add_edge("summary_generation", "performance_records")
    workflow.add_edge("performance_records", "storage_response")
    workflow.add_edge("storage_response", END)
    
    return workflow.compile()

async def sse_generator(meeting_id: str, state: Dict[str, Any]):
    workflow = create_workflow()
    
    # Initialize state properly
    initial_state = {
        "meetingId": meeting_id,
        "auth_token": state["auth_token"],
        "organizationId": "",
        "departmentId": None,
        "botId": None,
        "meeting_data": None,
        "participants": [],
        "attendees": [],
        "audioUrl": None,
        "videoUrl": None,
        "transcription": None,
        "meetingSummary": None,
        "tasks": None,
        "generatedContent": None,
        "messages": [],
        "status": "pending",
        "initial_ids": {},
        "generate_summary": True,
        "tasks_detected": False,
        "content_detected": False,
        "content_details": None,
        "parallel_results": None
    }
    
    try:
        logger.debug(f"Starting workflow for meeting {meeting_id}")
        
        final_state = None
        
        # Stream the workflow execution - this runs the workflow ONCE
        async for output in workflow.astream(initial_state):
            logger.debug(f"Workflow output: {output}")
            
            # Extract the node name and its output
            for node_name, node_output in output.items():
                if node_output:
                    # Store the final state as we go
                    final_state = node_output
                    
                    progress_message = f"Completed {node_name}"
                    yield {
                        "event": "progress", 
                        "data": json.dumps({
                            "message": progress_message,
                            "node": node_name,
                            "status": "processing"
                        })
                    }
        
        # At this point, final_state contains the complete result
        if not final_state:
            raise Exception("Workflow completed but no final state was captured")
            
        logger.debug(f"Final state keys: {final_state.keys()}")
        
        # Convert HumanMessage objects to serializable strings
        messages = final_state.get("messages", [])
        serializable_messages = []
        for msg in messages:
            if hasattr(msg, 'content'):
                serializable_messages.append(msg.content)
            else:
                serializable_messages.append(str(msg))
        
        # Prepare final response
        final_response = {
            "success": True,
            "meetingId": meeting_id,
            "status": "completed",
            "data": {
                "meetingSummary": final_state.get("meetingSummary"),
                "tasks": final_state.get("tasks", []),
                "generatedContent": final_state.get("generatedContent", []),
                "messages": serializable_messages,
                "initial_ids": final_state.get("initial_ids", {})
            }
        }
        
        yield {"event": "complete", "data": json.dumps(final_response)}
        
    except Exception as e:
        logger.error(f"Error in SSE pipeline for meeting {meeting_id}: {str(e)}", exc_info=True)
        error_response = {
            "success": False,
            "message": f"Pipeline failed: {str(e)}",
            "status": "failure",
            "data": {}
        }
        yield {"event": "error", "data": json.dumps(error_response)}

@app.post("/process")
async def process_meeting(request: ProcessRequest, fastapi_request: Request):
    try:
        # Get auth_token from request.state (set by middleware)
        auth_token = fastapi_request.state.auth_token
        logger.debug(f"Starting pipeline for meeting {request.meeting_id}")
        return EventSourceResponse(sse_generator(request.meeting_id, {"auth_token": auth_token}))
    except Exception as e:
        logger.error(f"Error initializing pipeline for meeting {request.meeting_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Meeting processing pipeline is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)