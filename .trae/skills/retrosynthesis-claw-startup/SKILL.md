---
name: "retrosynthesis-claw-startup"
description: "Provides step-by-step instructions for starting the RetrosynthesisClaw project's frontend and backend servers. Invoke when user needs to run the project or asks about startup procedures."
---

# RetrosynthesisClaw Startup Guide

This skill provides comprehensive instructions for starting the RetrosynthesisClaw project's frontend and backend servers, ensuring the system is fully operational for molecule synthesis planning.

## When to Invoke

Invoke this skill when:
- User needs to run the RetrosynthesisClaw project
- User asks about startup procedures
- User encounters issues starting the servers
- User wants to test the project's functionality
- User needs to verify server status

## Prerequisites

Before starting the servers, ensure you have:
- Python 3.9+ installed
- Required dependencies installed (see `requirements.txt`)
- Local LLM service (e.g., Ollama) running if using local models
- Access to the project directory

## Backend Server Startup

### Step 1: Navigate to Project Root
```bash
cd path/to/RetrosynthesisClaw
```

### Step 2: Start Backend API Server
```bash
# Development mode (with auto-reload)
uvicorn src.retrosynthesis_claw.api:app --host 0.0.0.0 --port 8000 --reload

# Production mode (without reload)
uvicorn src.retrosynthesis_claw.api:app --host 0.0.0.0 --port 8000
```

### Step 3: Verify Backend Status
Check if the backend is running by accessing:
```
http://localhost:8000/health
```

Expected response:
```json
{"status":"ok"}
```

## Frontend Server Startup

### Step 1: Navigate to Frontend Directory
```bash
cd path/to/RetrosynthesisClaw/frontend
```

### Step 2: Start Frontend Server
```bash
# Using Python's built-in HTTP server
python -m http.server 8001

# Alternative: Using Node.js (if available)
npx http-server -p 8001
```

### Step 3: Verify Frontend Status
Check if the frontend is running by accessing:
```
http://localhost:8001
```

## Accessing the Application

You can access the application through either:
- **Frontend server**: http://localhost:8001
- **Backend server**: http://localhost:8000/frontend

## Common Issues and Solutions

### Port Already in Use
If you get a "port already in use" error:

1. Find the process using the port:
   ```bash
   netstat -ano | findstr :8000
   ```

2. Terminate the process:
   ```bash
   taskkill /PID <process_id> /F
   ```

3. Restart the server with a different port if needed:
   ```bash
   uvicorn src.retrosynthesis_claw.api:app --host 0.0.0.0 --port 8002 --reload
   ```

### Frontend Cannot Connect to Backend
Ensure the frontend's API base URL matches the backend port:

1. Edit `frontend/script.js`:
   ```javascript
   const API_BASE_URL = 'http://localhost:8000'; // Update port if changed
   ```

2. Edit `frontend/index.html` (for Ketcher integration):
   ```html
   <iframe src="http://localhost:8000/standalone/index.html"></iframe>
   ```

### Server Startup Failures

- **ModuleNotFoundError**: Ensure you're in the project root directory
- **Dependency Issues**: Run `pip install -r requirements.txt`
- **LLM Connection Issues**: Verify your LLM service is running

## Testing the System

To test the system functionality:

1. Open the frontend at http://localhost:8001
2. Enter a molecule SMILES (e.g., `BrC1=C2CCCOC2=NC=C1`)
3. Click "Generate Routes"
4. Wait for the synthesis routes to be generated
5. Verify the output includes:
   - Molecule structure
   - Synthesis strategy
   - Multiple synthetic routes
   - Route evaluation

## Server Status Check

### Backend Status
- **Health Check**: http://localhost:8000/health
- **API Documentation**: http://localhost:8000/docs

### Frontend Status
- **Home Page**: http://localhost:8001
- **Monitor Page**: http://localhost:8001/agent-monitor.html
- **API Config Page**: http://localhost:8001/api-config.html

## Shutdown Procedure

To stop the servers:

1. For backend server: Press `Ctrl+C` in the terminal
2. For frontend server: Press `Ctrl+C` in the terminal

## Troubleshooting Tips

- **Clear Browser Cache**: Sometimes cached files can cause issues
- **Check Console Logs**: Use browser developer tools to check for errors
- **Verify Network Connectivity**: Ensure no firewall is blocking ports
- **Check Server Logs**: Review terminal output for error messages

This guide provides all the necessary steps to start and maintain the RetrosynthesisClaw project's servers, ensuring a smooth user experience for molecule synthesis planning.