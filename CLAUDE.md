# 🤖 CLAUDE.md - Projet 4: AI Agent Autonome / Agentic Workflow

## 📌 Objectif du Projet
Créer un agent IA capable de réaliser des tâches complexes de manière autonome. L'agent utilisera des outils, prendra des décisions, et itérera vers une solution. Cet agent analysera des fichiers CSV et générera des insights automatiques.

---

## 🛠️ Stack Technologique

### Backend
- **Framework :** FastAPI
- **LLM :** Claude 3.5 Sonnet (Anthropic)
- **Tool Management :** Claude tool_use (native)
- **Data Analysis :** Pandas, NumPy
- **Visualization :** Matplotlib, Plotly
- **Database :** SQLite (job storage)

### Frontend
- **Framework :** React 18 + Vite
- **Styling :** Tailwind CSS
- **Charts :** Plotly.js
- **Real-time :** WebSockets
- **File Upload :** React Dropzone

### Infrastructure
- **Backend :** Railway.app
- **Frontend :** Vercel
- **Task Queue :** Optional Celery (for heavy computations)

---

## 📐 Architecture Agent

```
┌─────────────────────────────────────────┐
│         Frontend (React)                 │
│  ┌─────────────────────────────────┐   │
│  │ CSV Upload Interface            │   │
│  │ Agent Progress Display          │   │
│  │ Results & Visualizations        │   │
│  └────────────┬────────────────────┘   │
│               │                        │
│      (REST + WebSocket)               │
│               │                        │
│  ┌────────────▼────────────────────┐   │
│  │ Backend (FastAPI)               │   │
│  │ ┌──────────────────────────────┐│   │
│  │ │ Agent Controller             ││   │
│  │ │ ┌────────────────────────────┐││   │
│  │ │ │ Step 1: Load CSV Data     │││   │
│  │ │ │ Step 2: Explore Stats     │││   │
│  │ │ │ Step 3: Detect Issues     │││   │
│  │ │ │ Step 4: Analyze Patterns  │││   │
│  │ │ │ Step 5: Generate Report   │││   │
│  │ │ └────────────────────────────┘││   │
│  │ └──────────────────────────────┘│   │
│  └────────────┬────────────────────┘   │
│               │                        │
│    ┌──────────▼──────────┐            │
│    │ Tool Executors:     │            │
│    │ • read_csv          │            │
│    │ • statistics        │            │
│    │ • detect_outliers   │            │
│    │ • correlation       │            │
│    │ • create_chart      │            │
│    │ • generate_report   │            │
│    └─────────────────────┘            │
│                                       │
└───────────────────────────────────────┘
```

---

## 📋 Phase 1: Project Setup

### 1.1 Directory Structure

```bash
mkdir data-analysis-agent
cd data-analysis-agent

mkdir -p backend frontend
mkdir -p backend/app/{api,tools,models,schemas}
mkdir -p backend/uploads backend/outputs
mkdir -p frontend/src/{components,pages,services}

cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn anthropic pandas numpy matplotlib plotly python-multipart python-dotenv aiofiles
```

### 1.2 Environment Setup

**Backend `.env`**
```
ANTHROPIC_API_KEY=sk-ant-...
API_PORT=8000
CORS_ORIGINS=["http://localhost:5173"]
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_FILE_SIZE=52428800  # 50MB
```

---

## 📋 Phase 2: Backend - Tool Implementation

### 2.1 Tool Definitions

**File: `backend/app/tools/definitions.py`**
```python
from typing import Any, Callable
import json

class Tool:
    def __init__(self, name: str, description: str, input_schema: dict, handler: Callable):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
    
    def to_dict(self) -> dict:
        """Convert to Claude tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.input_schema,
                "required": list(self.input_schema.keys())
            }
        }

# Tool definitions
TOOLS = [
    Tool(
        name="read_csv",
        description="Load a CSV file and return basic information about its structure",
        input_schema={
            "file_path": {
                "type": "string",
                "description": "Path to the CSV file"
            }
        },
        handler=None  # Set in handlers.py
    ),
    Tool(
        name="describe_statistics",
        description="Calculate descriptive statistics (mean, median, std, quantiles) for numeric columns",
        input_schema={
            "file_path": {
                "type": "string",
                "description": "Path to the CSV file"
            },
            "columns": {
                "type": "array",
                "description": "List of column names to analyze (empty = all)",
                "items": {"type": "string"}
            }
        },
        handler=None
    ),
    Tool(
        name="detect_outliers",
        description="Detect outliers using IQR or Z-score method",
        input_schema={
            "file_path": {
                "type": "string",
                "description": "Path to the CSV file"
            },
            "method": {
                "type": "string",
                "enum": ["iqr", "zscore"],
                "description": "Outlier detection method"
            },
            "column": {
                "type": "string",
                "description": "Column to analyze for outliers"
            }
        },
        handler=None
    ),
    Tool(
        name="correlation_analysis",
        description="Calculate correlation matrix between numeric columns",
        input_schema={
            "file_path": {
                "type": "string",
                "description": "Path to the CSV file"
            }
        },
        handler=None
    ),
    Tool(
        name="create_visualization",
        description="Generate a chart for visualization",
        input_schema={
            "file_path": {
                "type": "string",
                "description": "Path to the CSV file"
            },
            "chart_type": {
                "type": "string",
                "enum": ["histogram", "scatter", "heatmap", "timeseries", "boxplot"],
                "description": "Type of chart"
            },
            "x_column": {
                "type": "string",
                "description": "Column for X axis"
            },
            "y_column": {
                "type": "string",
                "description": "Column for Y axis (optional)"
            },
            "title": {
                "type": "string",
                "description": "Chart title"
            }
        },
        handler=None
    ),
    Tool(
        name="generate_report",
        description="Compile analysis findings into a markdown report",
        input_schema={
            "title": {
                "type": "string",
                "description": "Report title"
            },
            "findings": {
                "type": "array",
                "description": "List of findings to include",
                "items": {"type": "string"}
            }
        },
        handler=None
    )
]

def get_tools_for_claude():
    """Format tools for Claude API"""
    return [tool.to_dict() for tool in TOOLS]
```

### 2.2 Tool Implementations

**File: `backend/app/tools/handlers.py`**
```python
import pandas as pd
import numpy as np
import json
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px

class DataAnalysisTools:
    @staticmethod
    def read_csv(file_path: str) -> dict:
        """Read CSV and return basic info"""
        try:
            df = pd.read_csv(file_path)
            
            return {
                "success": True,
                "shape": df.shape,
                "columns": df.columns.tolist(),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "missing_values": df.isnull().sum().to_dict(),
                "head": df.head(5).to_dict(orient='records')
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def describe_statistics(file_path: str, columns: list = None) -> dict:
        """Calculate statistics for numeric columns"""
        try:
            df = pd.read_csv(file_path)
            
            if columns:
                df = df[columns]
            
            stats = df.describe().to_dict()
            
            # Add skewness and kurtosis
            for col in df.select_dtypes(include=[np.number]).columns:
                stats[col]['skewness'] = float(df[col].skew())
                stats[col]['kurtosis'] = float(df[col].kurtosis())
            
            return {
                "success": True,
                "statistics": stats
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def detect_outliers(file_path: str, method: str = "iqr", column: str = None) -> dict:
        """Detect outliers"""
        try:
            df = pd.read_csv(file_path)
            
            if not column or column not in df.columns:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                column = numeric_cols[0] if numeric_cols else None
            
            if not column:
                return {"success": False, "error": "No numeric column found"}
            
            data = df[column].dropna()
            
            if method == "iqr":
                Q1 = data.quantile(0.25)
                Q3 = data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
            
            elif method == "zscore":
                z_scores = np.abs((data - data.mean()) / data.std())
                outliers = df[np.abs((df[column] - df[column].mean()) / df[column].std()) > 3]
            
            return {
                "success": True,
                "outlier_count": len(outliers),
                "percentage": f"{(len(outliers)/len(df)*100):.2f}%",
                "outlier_values": outliers[column].tolist()[:10]  # First 10
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def correlation_analysis(file_path: str) -> dict:
        """Calculate correlation matrix"""
        try:
            df = pd.read_csv(file_path)
            numeric_df = df.select_dtypes(include=[np.number])
            
            correlation_matrix = numeric_df.corr().to_dict()
            
            # Find strongest correlations
            corr_pairs = []
            for i, col1 in enumerate(numeric_df.columns):
                for col2 in numeric_df.columns[i+1:]:
                    corr_value = correlation_matrix[col1][col2]
                    if abs(corr_value) > 0.5:  # Only strong correlations
                        corr_pairs.append({
                            "column1": col1,
                            "column2": col2,
                            "correlation": float(corr_value)
                        })
            
            return {
                "success": True,
                "correlation_matrix": correlation_matrix,
                "strong_correlations": sorted(corr_pairs, key=lambda x: abs(x["correlation"]), reverse=True)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def create_visualization(
        file_path: str,
        chart_type: str,
        x_column: str,
        y_column: str = None,
        title: str = "Chart"
    ) -> dict:
        """Generate visualization"""
        try:
            df = pd.read_csv(file_path)
            
            if chart_type == "histogram":
                fig = px.histogram(df, x=x_column, title=title)
            
            elif chart_type == "scatter":
                fig = px.scatter(df, x=x_column, y=y_column, title=title)
            
            elif chart_type == "heatmap":
                numeric_df = df.select_dtypes(include=[np.number])
                corr_matrix = numeric_df.corr()
                fig = go.Figure(data=go.Heatmap(z=corr_matrix.values, x=corr_matrix.columns, y=corr_matrix.columns))
                fig.update_layout(title=title)
            
            elif chart_type == "boxplot":
                fig = px.box(df, y=x_column, title=title)
            
            elif chart_type == "timeseries" and y_column:
                fig = px.line(df, x=x_column, y=y_column, title=title)
            
            # Save and return path
            output_path = f"./outputs/{title.replace(' ', '_')}.html"
            fig.write_html(output_path)
            
            return {
                "success": True,
                "chart_path": output_path,
                "chart_type": chart_type
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def generate_report(title: str, findings: list) -> dict:
        """Generate markdown report"""
        try:
            markdown = f"""# {title}

Generated by AI Analysis Agent

## Executive Summary

The following analysis was performed on the dataset.

## Key Findings

"""
            
            for i, finding in enumerate(findings, 1):
                markdown += f"\n### Finding {i}\n{finding}\n"
            
            markdown += "\n---\n*Report generated automatically*"
            
            # Save report
            report_path = f"./outputs/{title.replace(' ', '_')}_report.md"
            Path(report_path).write_text(markdown)
            
            return {
                "success": True,
                "report_path": report_path,
                "report": markdown
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
```

---

## 📋 Phase 3: Agent Logic

### 3.1 Agent Controller

**File: `backend/app/agent.py`**
```python
import anthropic
import json
from datetime import datetime
import os
from app.tools.definitions import TOOLS, get_tools_for_claude
from app.tools.handlers import DataAnalysisTools

class DataAnalysisAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-3-5-sonnet-20241022"
        self.tools = get_tools_for_claude()
        self.tool_handlers = {
            "read_csv": DataAnalysisTools.read_csv,
            "describe_statistics": DataAnalysisTools.describe_statistics,
            "detect_outliers": DataAnalysisTools.detect_outliers,
            "correlation_analysis": DataAnalysisTools.correlation_analysis,
            "create_visualization": DataAnalysisTools.create_visualization,
            "generate_report": DataAnalysisTools.generate_report,
        }
        self.steps = []
    
    async def analyze(self, file_path: str, user_request: str):
        """Run agent analysis loop"""
        
        self.steps = []
        messages = [
            {
                "role": "user",
                "content": f"""You are a data analysis AI agent. A CSV file has been uploaded at: {file_path}

User request: {user_request}

Analyze the data and provide comprehensive insights.
Use the available tools to:
1. Read and understand the data structure
2. Calculate descriptive statistics
3. Detect outliers and anomalies
4. Analyze correlations
5. Create visualizations
6. Generate a final report

Start by reading the CSV file."""
            }
        ]
        
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            # Call Claude with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=self.tools,
                messages=messages
            )
            
            # Log step
            step_info = {
                "iteration": iteration,
                "stop_reason": response.stop_reason,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Check if done
            if response.stop_reason == "end_turn":
                # Extract final response
                final_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text = block.text
                
                step_info["type"] = "completion"
                step_info["message"] = final_text
                self.steps.append(step_info)
                
                return {
                    "status": "completed",
                    "result": final_text,
                    "steps": self.steps
                }
            
            # Process tool calls
            if response.stop_reason == "tool_use":
                step_info["type"] = "tool_use"
                step_info["tools_used"] = []
                
                # Add assistant message
                messages.append({"role": "assistant", "content": response.content})
                
                tool_results = []
                
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        
                        # Log tool usage
                        step_info["tools_used"].append({
                            "name": tool_name,
                            "input": tool_input
                        })
                        
                        # Execute tool
                        handler = self.tool_handlers.get(tool_name)
                        if handler:
                            result = handler(**tool_input)
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })
                
                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})
                self.steps.append(step_info)
            
            iteration += 1
        
        return {
            "status": "error",
            "error": "Max iterations reached",
            "steps": self.steps
        }
```

---

## 📋 Phase 4: FastAPI Routes

### 4.1 API Endpoints

**File: `backend/app/main.py`**
```python
from fastapi import FastAPI, UploadFile, File, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import uuid
import json

from app.agent import DataAnalysisAgent

load_dotenv()

app = FastAPI(title="Data Analysis Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
Path("./uploads").mkdir(exist_ok=True)
Path("./outputs").mkdir(exist_ok=True)

# Global agent instance
agent = DataAnalysisAgent()

# In-memory job storage (use DB in production)
jobs = {}

@app.post("/api/analyze")
async def start_analysis(
    file: UploadFile = File(...),
    request_text: str = "Analyze this data and provide insights"
):
    """Start data analysis job"""
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Validate file
        if file.content_type not in ["text/csv", "application/vnd.ms-excel"]:
            raise HTTPException(status_code=400, detail="Only CSV files allowed")
        
        # Save file
        file_path = f"./uploads/{job_id}.csv"
        content = await file.read()
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Create job record
        jobs[job_id] = {
            "status": "running",
            "filename": file.filename,
            "file_path": file_path,
            "steps": [],
            "result": None
        }
        
        # Start analysis (async)
        asyncio.create_task(run_analysis_task(job_id, file_path, request_text))
        
        return {"job_id": job_id, "status": "started"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_analysis_task(job_id: str, file_path: str, request: str):
    """Background task for analysis"""
    try:
        result = await agent.analyze(file_path, request)
        jobs[job_id].update(result)
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]

@app.websocket("/ws/job/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    """WebSocket for real-time updates"""
    await websocket.accept()
    
    if job_id not in jobs:
        await websocket.close(code=4004, reason="Job not found")
        return
    
    last_step_count = 0
    
    try:
        while True:
            job = jobs.get(job_id, {})
            
            # Send new steps
            current_steps = job.get("steps", [])
            if len(current_steps) > last_step_count:
                for step in current_steps[last_step_count:]:
                    await websocket.send_json({
                        "type": "step",
                        "step": step
                    })
                last_step_count = len(current_steps)
            
            # Check if completed
            if job.get("status") in ["completed", "error"]:
                await websocket.send_json({
                    "type": "complete",
                    "status": job.get("status"),
                    "result": job.get("result")
                })
                break
            
            await asyncio.sleep(1)
    
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 📋 Phase 5: Frontend

### 5.1 Main Component

**File: `frontend/src/App.jsx`**
```jsx
import React, { useState } from 'react';
import CSVUpload from './components/CSVUpload';
import AgentProgress from './components/AgentProgress';
import './App.css';

function App() {
  const [jobId, setJobId] = useState(null);
  const [jobData, setJobData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async (file, requestText) => {
    setLoading(true);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('request_text', requestText);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/api/analyze`,
        {
          method: 'POST',
          body: formData
        }
      );

      const data = await response.json();
      setJobId(data.job_id);
    } catch (error) {
      console.error('Error starting analysis:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>🤖 Data Analysis Agent</h1>
        <p>Autonomous AI-powered data exploration</p>
      </header>

      <div className="container">
        {!jobId ? (
          <CSVUpload onUpload={handleUpload} loading={loading} />
        ) : (
          <AgentProgress jobId={jobId} />
        )}
      </div>
    </div>
  );
}

export default App;
```

### 5.2 Progress Component

**File: `frontend/src/components/AgentProgress.jsx`**
```jsx
import React, { useState, useEffect } from 'react';

export default function AgentProgress({ jobId }) {
  const [steps, setSteps] = useState([]);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('running');

  useEffect(() => {
    // Connect WebSocket
    const ws = new WebSocket(
      `${import.meta.env.VITE_API_URL.replace('http', 'ws')}/ws/job/${jobId}`
    );

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'step') {
        setSteps(prev => [...prev, data.step]);
      } else if (data.type === 'complete') {
        setStatus(data.status);
        setResult(data.result);
      }
    };

    return () => ws.close();
  }, [jobId]);

  return (
    <div className="agent-progress">
      <h2>Analysis in Progress...</h2>

      <div className="steps">
        {steps.map((step, idx) => (
          <div key={idx} className={`step ${step.type}`}>
            <span className="step-number">{idx + 1}</span>
            <div className="step-content">
              <div className="step-type">{step.type}</div>
              {step.tools_used && (
                <div className="tools-used">
                  {step.tools_used.map((tool, i) => (
                    <span key={i} className="tool-badge">{tool.name}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {result && (
        <div className="result">
          <h3>Analysis Complete</h3>
          <div className="result-text">{result}</div>
        </div>
      )}

      {status === 'error' && (
        <div className="error">Analysis failed</div>
      )}
    </div>
  );
}
```

---

## ✅ Checklist de Développement

- [ ] Tool definitions implémentées
- [ ] Tool handlers fonctionnels
- [ ] Agent controller complet
- [ ] FastAPI routes setup
- [ ] Upload CSV handling
- [ ] Agent analysis loop
- [ ] WebSocket integration
- [ ] Frontend React setup
- [ ] Progress display component
- [ ] Result display
- [ ] Error handling
- [ ] Testing with sample CSVs
- [ ] Deployment to Railway
- [ ] Deployment to Vercel
- [ ] Documentation

---

## 🎯 Critères de Succès

✅ Upload CSV → Agent analyze autonomously  
✅ Real-time progress updates via WebSocket  
✅ Multiple tool calls in sequence  
✅ Visualizations generated  
✅ Report generated  
✅ < 30 secondes pour analysis complète  
✅ GitHub repo avec exemples de CSVs  

---

**📅 Timeline estimée: 3-4 semaines**

Bonne chance! 🎯
