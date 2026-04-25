"""
Supply Chain Disruption Predictor Agent — Flask Backend
=======================================================
Implements a TRUE multi-step agentic loop that calls Gemini repeatedly,
executes tool functions, and maintains full conversational memory across steps.
"""

import os
import json
import re
import time
import datetime
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Fallback models to rotate through if rate limits are hit
GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-3-flash-preview"
]
GEMINI_MODEL_INDEX = 0
GEMINI_MODEL = GEMINI_MODELS[GEMINI_MODEL_INDEX]

# Initialize Client
client = genai.Client(api_key=GEMINI_API_KEY)

MAX_STEPS = 6
MAX_RETRIES = 5  # We will also rotate through models during these retries

# ---------------------------------------------------------------------------
# TOOL IMPLEMENTATIONS (structured mock data)
# ---------------------------------------------------------------------------

def get_news(region: str, keywords: str, timeframe: str) -> dict:
    """Fetch recent supply-chain-relevant news for a region using NewsAPI."""
    # NewsAPI configuration (using provided key)
    api_key = "f2fb6e54b1294129a463b3a9adc74467"
    
    # Build query
    query = f"({region} AND ({keywords} OR 'supply chain' OR 'disruption'))"
    
    # Calculate date range
    today = datetime.datetime.now()
    if "day" in timeframe.lower():
        delta = 2
    elif "week" in timeframe.lower():
        delta = 7
    else:
        delta = 30
    from_date = (today - datetime.timedelta(days=delta)).strftime('%Y-%m-%d')
    
    url = 'https://newsapi.org/v2/everything'
    params = {
        'q': query,
        'from': from_date,
        'sortBy': 'relevancy',
        'apiKey': api_key,
        'pageSize': 5,
        'language': 'en'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") == "ok":
            articles = data.get("articles", [])
            formatted_articles = []
            for art in articles:
                formatted_articles.append({
                    "headline": art.get("title"),
                    "source": art.get("source", {}).get("name"),
                    "date": art.get("publishedAt", "")[:10],
                    "severity": "medium", # Default as NewsAPI doesn't have severity
                    "summary": art.get("description")
                })
            
            return {
                "articles": formatted_articles,
                "articles_found": len(formatted_articles),
                "region": region,
                "keywords": keywords,
                "timeframe": timeframe,
                "retrieved_at": datetime.datetime.now().isoformat() + "Z"
            }
        else:
            # Fallback to local data if API fails or quota exceeded
            return {
                "error": f"NewsAPI error: {data.get('message', 'Unknown error')}",
                "articles": [],
                "articles_found": 0
            }
            
    except Exception as e:
        return {"error": f"Failed to fetch news: {str(e)}"}


def get_weather(region: str, timeframe: str) -> dict:
    """Fetch weather/climate disruption data for a region."""
    weather_db = {
        "southeast asia": {
            "current_conditions": "Tropical storm forming in South China Sea",
            "alerts": [
                {
                    "type": "Tropical Storm Warning",
                    "severity": "high",
                    "description": "Tropical Storm Maysak expected to make landfall in Vietnam "
                                   "within 72 hours. Winds up to 95 km/h.",
                    "affected_areas": ["Ho Chi Minh City port", "Cai Mep terminal", "inland logistics routes"],
                    "expected_duration": "5-7 days",
                },
                {
                    "type": "Flood Advisory",
                    "severity": "medium",
                    "description": "Monsoon-related flooding in central Thailand. Water levels "
                                   "rising in Chao Phraya basin.",
                    "affected_areas": ["Bangkok industrial zones", "Ayutthaya manufacturing belt"],
                    "expected_duration": "10-14 days",
                },
            ],
            "temperature": "31°C",
            "humidity": "89%",
            "sea_state": "Rough — 2.5m swells in South China Sea",
        },
        "east asia": {
            "current_conditions": "Seasonal transition — late spring weather patterns",
            "alerts": [
                {
                    "type": "Air Quality Warning",
                    "severity": "low",
                    "description": "Yellow dust storm from Gobi Desert affecting Korean peninsula "
                                   "logistics and port operations.",
                    "affected_areas": ["Busan port", "Incheon airport cargo"],
                    "expected_duration": "3-4 days",
                },
            ],
            "temperature": "18°C",
            "humidity": "55%",
            "sea_state": "Moderate — 1.2m swells",
        },
        "europe": {
            "current_conditions": "Unseasonably warm and dry across central Europe",
            "alerts": [
                {
                    "type": "Drought Warning",
                    "severity": "high",
                    "description": "Rhine and Danube river levels critically low. Barge capacity "
                                   "severely restricted across Germany and Netherlands.",
                    "affected_areas": ["Rhine corridor", "Rotterdam inland connections", "Duisburg port"],
                    "expected_duration": "3-6 weeks",
                },
            ],
            "temperature": "27°C",
            "humidity": "35%",
            "sea_state": "Calm — North Sea normal",
        },
        "north america": {
            "current_conditions": "Late spring storm system moving across Midwest",
            "alerts": [
                {
                    "type": "Severe Thunderstorm Watch",
                    "severity": "medium",
                    "description": "Strong convective systems expected across tornado alley. "
                                   "Potential for localized warehouse and logistics disruptions.",
                    "affected_areas": ["Memphis logistics hub", "Dallas-Fort Worth distribution centers"],
                    "expected_duration": "2-3 days",
                },
            ],
            "temperature": "22°C",
            "humidity": "62%",
            "sea_state": "Normal — Gulf of Mexico calm",
        },
    }

    region_lower = region.lower().strip()
    for key, data in weather_db.items():
        if key in region_lower or region_lower in key or any(
            w in key for w in region_lower.split()
        ):
            data["region"] = region
            data["timeframe"] = timeframe
            data["retrieved_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            return data

    return {
        "region": region,
        "timeframe": timeframe,
        "current_conditions": "No specific alerts for this region",
        "alerts": [],
        "temperature": "N/A",
        "humidity": "N/A",
        "sea_state": "N/A",
        "retrieved_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def get_supplier_data(product_id: str) -> dict:
    """Retrieve supplier and inventory data for a product."""
    supplier_db = {
        "PROD-001": {
            "product_name": "Advanced Automotive MCU (Microcontroller Unit)",
            "category": "Semiconductors — Automotive Grade",
            "suppliers": [
                {
                    "name": "TechSemi Corp",
                    "location": "Hsinchu, Taiwan",
                    "region": "East Asia",
                    "tier": 1,
                    "reliability_score": 92,
                    "lead_time_days": 45,
                    "capacity_utilization": "87%",
                    "risk_factors": ["earthquake zone", "single-source dependency", "geopolitical tension"],
                },
                {
                    "name": "SinoChip Manufacturing",
                    "location": "Shenzhen, China",
                    "region": "East Asia",
                    "tier": 1,
                    "reliability_score": 78,
                    "lead_time_days": 38,
                    "capacity_utilization": "94%",
                    "risk_factors": ["trade restrictions", "high utilization", "export controls"],
                },
                {
                    "name": "GlobalSemi Solutions",
                    "location": "Dresden, Germany",
                    "region": "Europe",
                    "tier": 2,
                    "reliability_score": 88,
                    "lead_time_days": 60,
                    "capacity_utilization": "72%",
                    "risk_factors": ["energy cost volatility", "long lead time"],
                },
            ],
            "current_inventory": {
                "units_on_hand": 12500,
                "days_of_supply": 18,
                "reorder_point": 15000,
                "status": "BELOW_REORDER_POINT",
            },
            "demand_forecast": {
                "next_30_days": 22000,
                "next_90_days": 68000,
                "trend": "increasing",
                "confidence": "high",
            },
        },
        "PROD-002": {
            "product_name": "Industrial Lithium Battery Pack",
            "category": "Energy Storage — Industrial",
            "suppliers": [
                {
                    "name": "PowerCell Asia",
                    "location": "Gwangju, South Korea",
                    "region": "East Asia",
                    "tier": 1,
                    "reliability_score": 95,
                    "lead_time_days": 30,
                    "capacity_utilization": "81%",
                    "risk_factors": ["lithium price volatility", "regulatory changes"],
                },
                {
                    "name": "BatteryWorks Vietnam",
                    "location": "Ho Chi Minh City, Vietnam",
                    "region": "Southeast Asia",
                    "tier": 1,
                    "reliability_score": 82,
                    "lead_time_days": 35,
                    "capacity_utilization": "76%",
                    "risk_factors": ["weather disruption", "infrastructure limitations"],
                },
            ],
            "current_inventory": {
                "units_on_hand": 5200,
                "days_of_supply": 26,
                "reorder_point": 4000,
                "status": "ADEQUATE",
            },
            "demand_forecast": {
                "next_30_days": 6000,
                "next_90_days": 19500,
                "trend": "stable",
                "confidence": "medium",
            },
        },
    }

    pid = product_id.upper().strip()
    if pid in supplier_db:
        data = supplier_db[pid]
        data["product_id"] = pid
        data["retrieved_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        return data

    # Generic fallback
    return {
        "product_id": pid,
        "product_name": f"Product {pid}",
        "category": "General",
        "suppliers": [
            {
                "name": "GenericSupplier A",
                "location": "Shanghai, China",
                "region": "East Asia",
                "tier": 1,
                "reliability_score": 80,
                "lead_time_days": 42,
                "capacity_utilization": "78%",
                "risk_factors": ["standard trade risks"],
            }
        ],
        "current_inventory": {
            "units_on_hand": 8000,
            "days_of_supply": 22,
            "reorder_point": 7000,
            "status": "ADEQUATE",
        },
        "demand_forecast": {
            "next_30_days": 10000,
            "next_90_days": 32000,
            "trend": "stable",
            "confidence": "medium",
        },
        "retrieved_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def optimize_routes(current_routes: list, risk_factors: list) -> dict:
    """Evaluate and optimize shipping/logistics routes given risk factors."""
    # Build some route-specific analysis
    optimized = []
    for i, route in enumerate(current_routes):
        route_str = route if isinstance(route, str) else json.dumps(route)

        # Determine risk level based on keywords
        route_risk = "low"
        delays = "0-1 days"
        concerns = []

        for rf in risk_factors:
            rf_lower = rf.lower() if isinstance(rf, str) else ""
            if any(kw in rf_lower for kw in ["storm", "flood", "weather", "typhoon"]):
                route_risk = "high"
                delays = "5-10 days"
                concerns.append("Weather disruption along route corridor")
            elif any(kw in rf_lower for kw in ["port", "congestion", "labor"]):
                route_risk = "high"
                delays = "3-7 days"
                concerns.append("Port congestion / labor disruption")
            elif any(kw in rf_lower for kw in ["tariff", "regulation", "customs", "trade"]):
                route_risk = "medium"
                delays = "2-5 days"
                concerns.append("Regulatory / customs delays expected")
            elif any(kw in rf_lower for kw in ["geopolitical", "conflict", "sanction"]):
                route_risk = "high"
                delays = "7-14 days"
                concerns.append("Geopolitical risk — route may be blocked")

        if not concerns:
            concerns.append("No major disruptions identified for this route")

        optimized.append({
            "original_route": route_str,
            "risk_level": route_risk,
            "estimated_delay": delays,
            "concerns": concerns,
        })

    # Generate alternative routes
    alternatives = [
        {
            "route": "Air freight via Anchorage hub → Final destination",
            "cost_premium": "+180-220%",
            "time_saved": "12-18 days",
            "risk_level": "low",
            "recommendation": "Use for critical/time-sensitive components only",
        },
        {
            "route": "Sea: Reroute via Cape of Good Hope (avoid Suez/Red Sea)",
            "cost_premium": "+25-35%",
            "time_saved": "-8 days (longer)",
            "risk_level": "low",
            "recommendation": "Viable for bulk shipments tolerant of delay",
        },
        {
            "route": "Rail: Trans-Siberian / China-Europe Express",
            "cost_premium": "+40-60%",
            "time_saved": "8-12 days vs sea",
            "risk_level": "medium",
            "recommendation": "Good middle ground — check geopolitical clearance",
        },
    ]

    return {
        "analysis_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "routes_analyzed": len(optimized),
        "route_assessments": optimized,
        "alternative_routes": alternatives,
        "overall_recommendation": (
            "Diversify shipping modes. Use air freight for critical items, "
            "re-route sea freight to avoid congested hubs, and pre-clear customs "
            "documentation to minimize regulatory delays."
        ),
    }


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------
TOOLS = {
    "get_news": get_news,
    "get_weather": get_weather,
    "get_supplier_data": get_supplier_data,
    "optimize_routes": optimize_routes,
}


def execute_tool(action: str, action_input: dict) -> dict:
    """Execute a tool by name with the given input dict."""
    if action not in TOOLS:
        return {"error": f"Unknown tool: {action}"}
    try:
        func = TOOLS[action]
        result = func(**action_input)
        return result
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}


# ---------------------------------------------------------------------------
# Gemini API caller
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an enterprise supply chain risk analysis agent.

You have access to the following tools:
1. get_news(region, keywords, timeframe) — Fetch recent supply chain news for a region
2. get_weather(region, timeframe) — Get weather and climate disruption data for a region
3. get_supplier_data(product_id) — Retrieve supplier, inventory, and demand data for a product
4. optimize_routes(current_routes, risk_factors) — Evaluate and optimize shipping routes

You MUST:
- Think step-by-step to build a comprehensive risk analysis
- Call tools one at a time to gather data before making conclusions
- NEVER hallucinate data — only use data returned by tools
- Maintain full context of previous steps
- Analyze ALL regions provided by the user
- Always check supplier data for the given product
- Always optimize routes after gathering risk factors

For each step, output STRICT JSON only (no markdown, no code fences):

{
  "step": <step_number>,
  "thought": "<your reasoning for this step>",
  "action": "<tool_name>",
  "action_input": {<tool_parameters>}
}

Use action "NONE" with null action_input ONLY when you are ready to give the final answer.

When you have gathered enough data (typically after 3-5 tool calls), output your final answer as:

{
  "step": <step_number>,
  "thought": "<final synthesis reasoning>",
  "action": "NONE",
  "action_input": null,
  "final_answer": {
    "risk_summary": "<comprehensive risk summary paragraph>",
    "disruptions_detected": ["<disruption 1>", "<disruption 2>", ...],
    "recommended_actions": ["<action 1>", "<action 2>", ...],
    "confidence_score": <0-100>,
    "risk_level": "<LOW | MEDIUM | HIGH | CRITICAL>"
  }
}

IMPORTANT: Output raw JSON only. No markdown formatting. No ```json blocks. Just the JSON object."""


def call_gemini(context: list, retry: int = 0) -> dict:
    """Call Gemini API using the new google-genai SDK with automatic model rotation."""
    global GEMINI_MODEL, GEMINI_MODEL_INDEX
    
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    try:
        print(f"🤖 Attempting analysis with: {GEMINI_MODEL} (Step retry: {retry})")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=context,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=2048,
                response_mime_type="application/json"
            )
        )

        text = response.text.strip()
        
        # Clean up: remove markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        parsed = json.loads(text)
        return parsed

    except (json.JSONDecodeError, Exception) as e:
        err_msg = str(e)
        # Check for quota or availability errors
        is_quota = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg
        is_unreachable = "503" in err_msg or "UNAVAILABLE" in err_msg or "timeout" in err_msg.lower()
        
        if retry < MAX_RETRIES:
            if is_quota or is_unreachable:
                # Rotate to the next model in our list
                GEMINI_MODEL_INDEX = (GEMINI_MODEL_INDEX + 1) % len(GEMINI_MODELS)
                GEMINI_MODEL = GEMINI_MODELS[GEMINI_MODEL_INDEX]
                print(f"⚠️ Model error ({'Quota' if is_quota else 'Unreachable'}). Rotating to: {GEMINI_MODEL}")
                wait_time = 3 # Small cooldown before switching models
            else:
                wait_time = 5 * (retry + 1)
            
            print(f"⏳ Retrying (attempt {retry+1}/{MAX_RETRIES}) in {wait_time}s...")
            time.sleep(wait_time)
            return call_gemini(context, retry + 1)
            
        return {
            "step": 0,
            "thought": f"Failed after {MAX_RETRIES} retries. Final error: {err_msg}",
            "action": "NONE",
            "action_input": None,
            "final_answer": {
                "risk_summary": "All model fallbacks were exhausted or reached capacity. Please try again in 60 seconds.",
                "disruptions_detected": ["Global API Quota Limit Reached"],
                "recommended_actions": ["Wait for quota reset", "Switch to a paid API tier"],
                "confidence_score": 0,
                "risk_level": "UNKNOWN",
            },
        }


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------
def run_agent(product_id: str, regions: list, routes: list) -> dict:
    """Execute the multi-step agentic loop."""
    steps = []
    context = []

    # Initial user message
    user_message = (
        f"Analyze supply chain risks for:\n"
        f"- Product ID: {product_id}\n"
        f"- Regions: {', '.join(regions)}\n"
        f"- Current Routes: {', '.join(routes)}\n\n"
        f"Gather data using available tools, then provide a comprehensive risk assessment. "
        f"Start by checking the supplier data, then investigate news and weather for each "
        f"region, and finally optimize the routes based on discovered risks."
    )

    context.append({
        "role": "user",
        "parts": [{"text": user_message}],
    })

    final_answer = None

    for step_num in range(1, MAX_STEPS + 1):
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        # Call Gemini with full context
        response = call_gemini(context)

        # Ensure step number is correct
        response["step"] = step_num
        response["timestamp"] = timestamp

        # Check for final answer
        if "final_answer" in response and response.get("action", "NONE") == "NONE":
            response["observation"] = None
            steps.append(response)
            final_answer = response["final_answer"]
            break

        # Execute tool if action is specified and not NONE
        action = response.get("action", "NONE")
        action_input = response.get("action_input")

        if action and action != "NONE" and action_input:
            tool_result = execute_tool(action, action_input)
            response["observation"] = tool_result
        else:
            response["observation"] = None
            # If action is NONE but no final_answer, treat as completion needed
            steps.append(response)
            continue

        steps.append(response)

        # Add LLM response to context as model message
        context.append({
            "role": "model",
            "parts": [{"text": json.dumps({
                "step": step_num,
                "thought": response.get("thought", ""),
                "action": action,
                "action_input": action_input,
            })}],
        })

        # Add tool result as user message (observation)
        context.append({
            "role": "user",
            "parts": [{"text": f"Tool Result for {action}:\n{json.dumps(tool_result, indent=2)}"}],
        })

    # If we exhausted steps without a final answer, generate one
    if final_answer is None:
        context.append({
            "role": "user",
            "parts": [{"text": (
                "You have used all available steps. You MUST now provide your final_answer "
                "based on all the data you have gathered. Output the final JSON with "
                "final_answer field."
            )}],
        })
        response = call_gemini(context)
        response["step"] = len(steps) + 1
        response["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        response["observation"] = None
        steps.append(response)
        final_answer = response.get("final_answer", {
            "risk_summary": "Analysis completed with available data.",
            "disruptions_detected": [],
            "recommended_actions": [],
            "confidence_score": 50,
            "risk_level": "MEDIUM",
        })

    return {
        "steps": steps,
        "final_answer": final_answer,
        "total_steps": len(steps),
        "completed_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    """Main analysis endpoint."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        product_id = data.get("product_id", "").strip()
        regions = data.get("regions", [])
        routes = data.get("routes", [])

        if not product_id:
            return jsonify({"error": "product_id is required"}), 400
        if not regions:
            return jsonify({"error": "At least one region is required"}), 400
        if not routes:
            return jsonify({"error": "At least one route is required"}), 400

        result = run_agent(product_id, regions, routes)
        return jsonify(result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
        "model": GEMINI_MODEL,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("⚠️  WARNING: GEMINI_API_KEY environment variable is not set!")
        print("   Set it with: export GEMINI_API_KEY='your-key-here'")
    else:
        print(f"✅ Gemini API key configured (model: {GEMINI_MODEL})")

    print("🚀 Starting Supply Chain Disruption Predictor Agent...")
    app.run(debug=True, port=5001)
