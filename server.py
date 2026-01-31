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


# Initialize Gemini
import google.generativeai as genai
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Initialize ArmorIQ SDK
from armoriq_sdk import ArmorIQClient

ARMORIQ_API_KEY = os.getenv("ARMORIQ_API_KEY")
USER_ID = os.getenv("USER_ID", "doctor_admin")
AGENT_ID = os.getenv("AGENT_ID", "agent_prescription_gen")

class GeneratePrescriptionParams(BaseModel):
    pid: str
    prompt: str

@app.post("/generate-prescription")
async def generate_prescription_endpoint(params: GeneratePrescriptionParams):
    """
    Generate prescription directly via MCP server (Single Step)
    """
    try:
        # 0. ArmorIQ Plan Capture & Security Check
        is_verified = False
        plan_id = None
        
        if ARMORIQ_API_KEY:
            try:
                armoriq = ArmorIQClient(
                    api_key=ARMORIQ_API_KEY,
                    user_id=USER_ID,
                    agent_id=AGENT_ID
                )
                
                # Capture the execution plan for ArmorIQ dashboard
                plan = {
                    "steps": [
                        {
                            "action": "fetch_patient_data",
                            "mcp": "patient-data-mcp",
                            "description": "Retrieve patient medical history from Supabase",
                            "metadata": {
                                "pid": params.pid,
                                "data_source": "supabase"
                            }
                        },
                        {
                            "action": "generate_prescription",
                            "mcp": "gemini-ai-mcp",
                            "description": "Generate AI prescription using Gemini 2.5 Flash",
                            "metadata": {
                                "model": "gemini-2.5-flash",
                                "prompt_type": "ayurvedic_prescription"
                            }
                        },
                        {
                            "action": "verify_intent",
                            "mcp": "armoriq-security-mcp",
                            "description": "Verify prescription safety and HIPAA compliance",
                            "metadata": {
                                "compliance": "HIPAA"
                            }
                        }
                    ]
                }
                
                # Capture the plan with metadata
                plan_capture = armoriq.capture_plan(
                    llm="gemini-2.5-flash",
                    prompt=params.prompt,
                    plan=plan,
                    metadata={
                        "purpose": "prescription_generation",
                        "compliance": "HIPAA",
                        "tags": ["healthcare", "ai-prescription", "ayurveda"],
                        "patient_id_hash": params.pid[:8] + "...",  # Anonymized for privacy
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                print(f"✅ Plan structure validated locally")
                
                # IMPORTANT: capture_plan() only validates locally
                # We need to call get_intent_token() to actually submit to ArmorIQ backend
                try:
                    intent_token = armoriq.get_intent_token(
                        plan_capture=plan_capture,
                        validity_seconds=3600.0  # 1 hour validity
                    )
                    
                    # Extract plan_id from the intent token
                    plan_id = intent_token.plan_id if hasattr(intent_token, 'plan_id') else None
                    
                    if plan_id:
                        is_verified = True
                        print(f"✅ ArmorIQ Plan Submitted: {plan_id}")
                        print(f"   View in dashboard: https://dashboard.armoriq.ai")
                    else:
                        is_verified = False
                        print(f"⚠️ ArmorIQ: Plan submitted but no ID returned")
                        
                except Exception as token_error:
                    # If token generation fails, still mark plan as captured locally
                    print(f"⚠️ ArmorIQ Token Error: {token_error}")
                    print(f"   Plan validated locally but not submitted to backend")
                    is_verified = False
                    plan_id = None
                    
            except Exception as e:
                print(f"ArmorIQ Check Failed: {e}")
                is_verified = False


        # 1. Fetch Patient Data
        fetch_args = {"pid": params.pid, "include_prescriptions": True, "include_appointments": True}
        patient_data_full = await fetch_patient_data(fetch_args)
        
        # 2. Extract Data for Prompt
        patient = patient_data_full.get("patient", {})
        recent_appts = patient_data_full.get("appointments", [])
        prev_prescriptions = patient_data_full.get("prescriptions", [])
        
        current_symptoms = "General consultation"
        if recent_appts:
            current_symptoms = recent_appts[0].get("chief_complaint") or current_symptoms

        location = f"{patient.get('city', 'Unknown')}, {patient.get('state', 'Unknown')}"
        
        # 3. Construct Prompt
        prompt_text = f"""
You are Dr. Manas AI, an expert Ayurvedic physician assistant. Generate a comprehensive, personalized prescription based on the following patient data:

**DOCTOR'S SPECIFIC INSTRUCTIONS:**
{params.prompt}

**PATIENT PROFILE:**
- Name: {patient.get('user', {}).get('name', 'Patient')}
- Age: {patient.get('age', 'Not specified')}
- Gender: {patient.get('gender', 'Not specified')}
- Location: {location}

**MEDICAL HISTORY:**
- Allergies: {', '.join(patient.get('allergies', []) or ['None'])}
- Current Medications: {', '.join(patient.get('current_medications', []) or ['None'])}
- Chronic Conditions: {', '.join(patient.get('chronic_conditions', []) or ['None'])}

**CURRENT CONSULTATION:**
- Complaint: {current_symptoms}

**OUTPUT FORMAT (STRICT JSON):**
{{
  "diagnosis": "Diagnosis based on symptoms",
  "symptoms": ["symptom1", "symptom2"],
  "medicines": [
    {{
      "name": "Medicine Name",
      "dosage": "Dosage",
      "frequency": "Frequency",
      "duration": "Duration (e.g. 7 days)",
      "notes": "Notes"
    }}
  ],
  "instructions": "Instructions",
  "dietAdvice": "Diet advice",
  "followUpDays": 7,
  "safetyNotes": "Safety notes"
}}
RESPOND ONLY WITH JSON.
"""

        # 4. Call Gemini
        if not GOOGLE_API_KEY:
             raise HTTPException(status_code=500, detail="Google API Key not configured on server")
             
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt_text)
        
        # 5. Parse JSON
        text = response.text
        # Simple cleanup to find JSON block
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
             raise ValueError("AI did not return valid JSON")
             
        json_str = json_match.group(0)
        prescription_data = json.loads(json_str)
        
        # Compatibility with frontend expectation
        # The frontend expects { prescription_content: "...", security_verified: bool } 
        # But for this endpoint, we might want to return the structured data directly or formatted text.
        # Let's return the structured JSON so the frontend can display it nicely.
        
        # However, the frontend 'page.tsx' currently expects a specific format if it calls this endpoint as a fallback.
        # Let's adjust to match what page.tsx expects in the catch block:
        # const fallbackData = await restResponse.json();
        # prescriptionText = fallbackData.prescription_content;
        
        # Let's format the JSON back to a string explicitly for display, 
        # OR better, update frontend to handle structured data.
        # For now, let's return a stringified version of the JSON for the 'prescription_content' field
        
        formatted_content = f"""
**Diagnosis:** {prescription_data.get('diagnosis')}
**Medicines:**
"""
        for med in prescription_data.get('medicines', []):
            formatted_content += f"- {med.get('name')} ({med.get('dosage')}, {med.get('frequency')}) for {med.get('duration')}\n"
            
        formatted_content += f"\n**Instructions:** {prescription_data.get('instructions')}\n"
        formatted_content += f"**Diet:** {prescription_data.get('dietAdvice')}\n"
        formatted_content += f"**Safety:** {prescription_data.get('safetyNotes')}"

        return JSONResponse(content={
            "prescription_content": formatted_content,
            "security_verified": is_verified,
            "raw_data": prescription_data,
            "armoriq_plan_id": plan_id  # Track ArmorIQ plan for audit trail
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
