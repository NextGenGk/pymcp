"""
FastAPI MCP Server for Patient Data
Provides fetch_patient_data tool to retrieve patient information from Supabase
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import json
from datetime import datetime, date

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Patient Data MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Pydantic Models
class MCPRequest(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class FetchPatientDataParams(BaseModel):
    pid: str = Field(..., description="Patient ID (UUID)")
    aid: Optional[str] = Field(None, description="Appointment ID (UUID) - optional")
    include_prescriptions: bool = Field(True, description="Include prescription history")
    include_appointments: bool = Field(True, description="Include appointment history")


# Custom JSON encoder for date/datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# MCP Protocol Handlers
@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest):
    """Main MCP request handler"""
    try:
        if request.method == "initialize":
            return MCPResponse(
                result={
                    "protocolVersion": "1.0",
                    "serverInfo": {
                        "name": "patient-data-mcp",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            )
        
        elif request.method == "tools/list":
            return MCPResponse(
                result={
                    "tools": [
                        {
                            "name": "fetch_patient_data",
                            "description": "Fetch comprehensive patient data from Supabase including demographics, medical history, appointments, and prescriptions.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "pid": {"type": "string"},
                                    "aid": {"type": "string"},
                                    "include_prescriptions": {"type": "boolean"},
                                    "include_appointments": {"type": "boolean"}
                                },
                                "required": ["pid"]
                            }
                        }
                    ]
                }
            )
        
        elif request.method == "tools/call":
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            if tool_name == "fetch_patient_data":
                result = await fetch_patient_data(arguments)
                return MCPResponse(result={"content": [{"type": "text", "text": json.dumps(result, cls=DateTimeEncoder, indent=2)}]})
            else:
                return MCPResponse(
                    error={
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                )
        
        else:
            return MCPResponse(
                error={
                    "code": -32601,
                    "message": f"Unknown method: {request.method}"
                }
            )
    
    except Exception as e:
        return MCPResponse(
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        )


async def fetch_patient_data(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch comprehensive patient data from Supabase
    
    Args:
        arguments: Dictionary containing pid, aid (optional), and flags for data inclusion
    
    Returns:
        Dictionary containing patient data, appointments, and prescriptions
    """
    try:
        # Validate and extract parameters
        params = FetchPatientDataParams(**arguments)
        
        # Fetch patient data with user information
        patient_response = supabase.table("patients").select(
            """
            *,
            users!patients_uid_fkey (
                uid,
                email,
                phone,
                name,
                profile_image_url,
                is_verified,
                is_active
            )
            """
        ).eq("pid", params.pid).execute()
        
        if not patient_response.data:
            raise HTTPException(status_code=404, detail=f"Patient not found with pid: {params.pid}")
        
        patient_data = patient_response.data[0]
        
        result = {
            "patient": patient_data,
            "appointments": [],
            "prescriptions": [],
            "current_appointment": None
        }
        
        # Fetch specific appointment if aid is provided
        if params.aid:
            appointment_response = supabase.table("appointments").select(
                """
                *,
                doctors!appointments_did_fkey (
                    did,
                    specialization,
                    qualification,
                    users!doctors_uid_fkey (
                        name,
                        email,
                        phone
                    )
                )
                """
            ).eq("aid", params.aid).eq("pid", params.pid).execute()
            
            if appointment_response.data:
                result["current_appointment"] = appointment_response.data[0]
        
        # Fetch appointment history if requested
        if params.include_appointments:
            appointments_response = supabase.table("appointments").select(
                """
                *,
                doctors!appointments_did_fkey (
                    did,
                    specialization,
                    qualification,
                    users!doctors_uid_fkey (
                        name,
                        email
                    )
                )
                """
            ).eq("pid", params.pid).order("scheduled_date", desc=True).limit(10).execute()
            
            result["appointments"] = appointments_response.data
        
        # Fetch prescription history if requested
        if params.include_prescriptions:
            prescriptions_response = supabase.table("prescriptions").select(
                """
                *,
                doctors!prescriptions_did_fkey (
                    did,
                    specialization,
                    qualification,
                    users!doctors_uid_fkey (
                        name
                    )
                )
                """
            ).eq("pid", params.pid).order("created_at", desc=True).limit(10).execute()
            
            result["prescriptions"] = prescriptions_response.data
        
        # Add metadata
        result["metadata"] = {
            "fetched_at": datetime.utcnow().isoformat(),
            "total_appointments": len(result["appointments"]),
            "total_prescriptions": len(result["prescriptions"])
        }
        
        return result
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching patient data: {str(e)}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Supabase connection
        supabase.table("patients").select("pid").limit(1).execute()
        
        status = {
            "status": "healthy", 
            "supabase": "connected"
        }
        return status
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
