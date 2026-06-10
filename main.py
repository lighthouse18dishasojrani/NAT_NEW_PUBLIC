import uuid
import asyncio
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# In-memory cache with simple TTL
analysis_db: Dict[str, Any] = {}

class CodeComparisonRequest(BaseModel):
    Old_code: str
    modified_code: str


@app.post("/api/compare")
async def compare_codes(request: CodeComparisonRequest):
    from ai_engine import (
        analyze_diff, business_logic_impact, 
        security_analysis, optimization_suggestions
    )
    
    Old_code = request.Old_code
    modified_code = request.modified_code
    request_id = str(uuid.uuid4())
    
    # Run all analysis functions concurrently using asyncio.gather
    diff_task = asyncio.create_task(
        asyncio.to_thread(analyze_diff, Old_code, modified_code)
    )
    impact_task = asyncio.create_task(
        asyncio.to_thread(business_logic_impact, Old_code, modified_code)
    )
    sec1_task = asyncio.create_task(
        asyncio.to_thread(security_analysis, Old_code)
    )
    sec2_task = asyncio.create_task(
        asyncio.to_thread(security_analysis, modified_code)
    )
    opt1_task = asyncio.create_task(
        asyncio.to_thread(optimization_suggestions, Old_code)
    )
    opt2_task = asyncio.create_task(
        asyncio.to_thread(optimization_suggestions, modified_code)
    )
    
    # Wait for all tasks to complete concurrently
    diff_res, impact_res, sec1, sec2, opt1, opt2 = await asyncio.gather(
        diff_task, impact_task, sec1_task, sec2_task, opt1_task, opt2_task
    )
    
    tests_res = "Disabled Due to Optimization"
    
    # Build analysis response
    analysis = {
        "type": "compare_result",
        "code1": Old_code,
        "code2": modified_code,
        "analysis": {
            "diff_analysis": diff_res,
            "business_impact": impact_res,
            "affected_test_cases": tests_res,
            "security_analysis": {"Disabled due to Optimization"},
            "optimization_suggestions": {
                "code1_optimization": opt1.get("details", ""), 
                "code2_optimization": opt2.get("details", "")
            }
        },
        "request_id": request_id
    }
    
    # Store in cache
    analysis_db[request_id] = analysis
    
    # Return JSON response directly (faster than default)
    return JSONResponse(
        content={
            "request_id": request_id,
            "url": f"http://localhost:8000/result?id={request_id}"
        }
    )


@app.get("/result", response_class=HTMLResponse)
async def result(request: Request, id: str = Query(...)):
    entry = analysis_db.get(id)
    if not entry:
        return HTMLResponse(
            f"<h2>No analysis found for ID {id}</h2>", 
            status_code=404
        )
    
    # Template rendering remains the same
    analysis = entry["analysis"]
    return templates.TemplateResponse("result.html", {
        "request": request,
        "code1": entry["code1"],
        "code2": entry["code2"],
        "a": analysis
    })


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse(
        "<h2>Welcome to Code Comparison API</h2>"
        "<p>Use POST /api/compare to compare codes.</p>"
    )
