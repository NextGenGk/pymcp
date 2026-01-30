# Patient Data MCP Server

A FastAPI-based Model Context Protocol (MCP) server that provides the `fetch_patient_data` tool to retrieve comprehensive patient information from Supabase for prescription generation.

## Features

- **fetch_patient_data** tool: Retrieves patient demographics, medical history, appointments, and prescriptions
- Supabase integration for secure database access
- MCP protocol compliant
- Comprehensive error handling
- Health check endpoint

## Installation

### Prerequisites

- Python 3.8 or higher
- Supabase account with the AuraSutra database schema
- pip package manager

### Setup Steps

1. **Navigate to the project directory:**

   ```bash
   cd mcp-patient-data
   ```

2. **Create a virtual environment (recommended):**

   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and add your Supabase credentials
   # SUPABASE_URL=https://your-project.supabase.co
   # SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   ```

   > **Where to find your Supabase credentials:**
   >
   > - Go to your Supabase project dashboard
   > - Navigate to Settings → API
   > - Copy the "Project URL" for `SUPABASE_URL`
   > - Copy the "service_role" key for `SUPABASE_SERVICE_ROLE_KEY`

## Running the Server

### Development Mode

```bash
uvicorn server:app --reload --port 8000
```

The server will start at `http://localhost:8000`

### Production Mode

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### Health Check

Test if the server is running and connected to Supabase:

```bash
curl http://localhost:8000/health
```

## MCP Client Configuration

### Claude Desktop Configuration

Add this to your Claude Desktop MCP settings file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "patient-data": {
      "command": "uvicorn",
      "args": ["server:app", "--host", "localhost", "--port", "8000"],
      "cwd": "C:\\Users\\atkol\\OneDrive\\Desktop\\aurav1\\mcp-patient-data",
      "env": {
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "your-service-role-key"
      }
    }
  }
}
```

> **Note:** Update the `cwd` path to match your actual installation directory.

## Tool Usage

### fetch_patient_data

Retrieves comprehensive patient data from Supabase.

#### Parameters

| Parameter               | Type          | Required | Default | Description                                       |
| ----------------------- | ------------- | -------- | ------- | ------------------------------------------------- |
| `pid`                   | string (UUID) | Yes      | -       | Patient ID                                        |
| `aid`                   | string (UUID) | No       | null    | Appointment ID (for specific appointment details) |
| `include_prescriptions` | boolean       | No       | true    | Include prescription history                      |
| `include_appointments`  | boolean       | No       | true    | Include appointment history                       |

#### Example Usage (via MCP Client)

```json
{
  "name": "fetch_patient_data",
  "arguments": {
    "pid": "123e4567-e89b-12d3-a456-426614174000",
    "aid": "987fcdeb-51a2-43f7-b123-456789abcdef",
    "include_prescriptions": true,
    "include_appointments": true
  }
}
```

#### Response Format

```json
{
  "patient": {
    "pid": "uuid",
    "uid": "uuid",
    "date_of_birth": "1990-01-01",
    "gender": "male",
    "blood_group": "O+",
    "allergies": ["penicillin"],
    "current_medications": ["aspirin"],
    "chronic_conditions": ["hypertension"],
    "users": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890"
    }
  },
  "current_appointment": {
    "aid": "uuid",
    "scheduled_date": "2026-01-31",
    "scheduled_time": "10:00:00",
    "chief_complaint": "Fever and headache",
    "symptoms": ["fever", "headache", "fatigue"],
    "doctors": {
      "specialization": ["General Medicine"],
      "qualification": "MBBS, MD"
    }
  },
  "appointments": [...],
  "prescriptions": [...],
  "metadata": {
    "fetched_at": "2026-01-31T01:52:00Z",
    "total_appointments": 5,
    "total_prescriptions": 3
  }
}
```

## Use Cases

### 1. Generate Prescription for Current Appointment

Fetch patient data with a specific appointment ID to get context for prescription generation:

```json
{
  "pid": "patient-uuid",
  "aid": "appointment-uuid"
}
```

### 2. Review Patient Medical History

Get comprehensive patient history without a specific appointment:

```json
{
  "pid": "patient-uuid",
  "include_prescriptions": true,
  "include_appointments": true
}
```

### 3. Quick Patient Lookup

Get only patient demographics without history:

```json
{
  "pid": "patient-uuid",
  "include_prescriptions": false,
  "include_appointments": false
}
```

## Database Schema

This MCP server works with the following Supabase tables:

- **patients**: Patient demographics and medical history
- **users**: User account information
- **appointments**: Appointment details and chief complaints
- **prescriptions**: Prescription history
- **doctors**: Doctor information and specializations

## Security Considerations

- **Never commit `.env` file**: The `.env` file contains sensitive credentials
- **Use service role key carefully**: The service role key bypasses Row Level Security (RLS)
- **Implement authentication**: Consider adding authentication to the MCP server for production use
- **Network security**: Run the server on localhost or behind a firewall

## Troubleshooting

### Connection Issues

If you get "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set" error:

- Verify `.env` file exists in the project directory
- Check that environment variables are correctly set
- Ensure no extra spaces in the `.env` file

### Patient Not Found

If you get "Patient not found" error:

- Verify the patient ID (pid) is correct
- Check that the patient exists in your Supabase database
- Ensure the service role key has proper permissions

### Import Errors

If you get module import errors:

- Activate your virtual environment
- Run `pip install -r requirements.txt` again
- Verify Python version is 3.8 or higher

## Development

### Project Structure

```
mcp-patient-data/
├── server.py              # Main FastAPI MCP server
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variable template
├── .env                  # Your actual credentials (gitignored)
└── README.md             # This file
```

### Adding New Tools

To add new MCP tools, modify `server.py`:

1. Add tool definition in `tools/list` handler
2. Implement tool function
3. Add tool call handler in `tools/call` method

## License

This project is part of the AuraSutra healthcare platform.

## Support

For issues or questions, please contact the development team.
