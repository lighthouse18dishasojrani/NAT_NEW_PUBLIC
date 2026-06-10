import difflib
import re
from datetime import datetime
from fpdf import FPDF
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Create a persistent session with connection pooling
def create_session():
    """Create optimized session with connection pooling and keep-alive"""
    session = requests.Session()
    
    # Configure connection pooling and retries
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
        backoff_factor=1
    )
    
    adapter = HTTPAdapter(
        pool_connections=10,      # Number of connection pools to cache
        pool_maxsize=10,          # Maximum connections to save in pool
        max_retries=retry_strategy,
        pool_block=False
    )
    
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session

# Global session for connection reuse
_session = create_session()

ENHANCED_SYSTEM_PROMPT = (
"You are an expert Oracle PL/SQL code analyzer with compiler-level precision.\n\n"
"CRITICAL ANALYSIS REQUIREMENTS:\n"
"- Examine EVERY character change, including single character differences\n"
"- Identify variable name typos (e.g., L_TOTAL_AdT vs L_TOTAL_AMT) as CRITICAL errors\n"
"- Catch subtle logic errors that could cause runtime failures\n"
"- Flag any change that could affect program behavior or data integrity\n"
"- Never dismiss changes as 'insignificant' - analyze potential impact\n\n"
"VARIABLE NAME ANALYSIS:\n"
"- Check for typos in variable names that could cause compilation errors\n"
"- Verify variable declarations match their usage\n"
"- Identify undefined variables or incorrect references\n"
"- Flag naming inconsistencies that could indicate bugs\n\n"
"LOGIC IMPACT SEVERITY LEVELS:\n"
"- CRITICAL: Will cause compilation failure or runtime errors\n"
"- HIGH: Changes business logic or calculation results\n"
"- MODERATE: Changes program flow or data processing\n"
"- LOW: Cosmetic changes with no functional impact\n\n"
"Be extremely precise and thorough. If you see a typo like 'AdT' instead of 'AMT', flag it as CRITICAL.\n"
)

def llm_analyze(prompt, system_prompt=None):
    """Optimized with persistent session and connection pooling"""
    try:
        if not OPENAI_API_KEY:
            return "Error: OPENAI_API_KEY not found in .env file"
            
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt or ENHANCED_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 2500
        }
        
        # Use persistent session instead of new connection each time
        response = _session.post(OPENAI_URL, headers=headers, json=body, timeout=90)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to OpenAI API: {e}"
    except Exception as e:
        return f"Analysis error: {e}"

def html_diff_highlight(orig, mod):
    import html

    def word_diff(a, b):
        a_words = a.split()
        b_words = b.split()
        sm = difflib.SequenceMatcher(None, a_words, b_words)
        result = []
        
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                result.extend([html.escape(word) + ' ' for word in b_words[j1:j2]])
            elif tag == 'replace':
                result.extend([f'<span class="removed">{html.escape(word)}</span> '
                              for word in a_words[i1:i2]])
                result.extend([f'<span class="added">{html.escape(word)}</span> '
                              for word in b_words[j1:j2]])
            elif tag == 'delete':
                result.extend([f'<span class="removed">{html.escape(word)}</span> '
                              for word in a_words[i1:i2]])
            elif tag == 'insert':
                result.extend([f'<span class="added">{html.escape(word)}</span> '
                              for word in b_words[j1:j2]])
        return ''.join(result)

    orig_lines = orig.splitlines()
    mod_lines = mod.splitlines()
    sm = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    result_lines = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for line in mod_lines[j1:j2]:
                result_lines.append(html.escape(line) + "<br>")
        elif tag in ['replace', 'insert']:
            for idx, line in enumerate(mod_lines[j1:j2]):
                cmp_line = orig_lines[i1 + idx] if tag == 'replace' and (i1 + idx) < len(orig_lines) else ""
                wl = word_diff(cmp_line, line)
                result_lines.append(wl + "<br>")
        elif tag == 'delete':
            for line in orig_lines[i1:i2]:
                result_lines.append(f'<span class="removed">{html.escape(line)}</span><br>')

    return ''.join(result_lines)

def analyze_code(code):
    return {"summary": "Disabled Due to Optimization"}

def analyze_diff(code1, code2):
    """Optimized diff analysis with shorter prompts"""
    char_diff = list(difflib.unified_diff(
        code1.splitlines(keepends=True), 
        code2.splitlines(keepends=True), 
        fromfile="Original", 
        tofile="Modified", 
        lineterm="", 
        n=3  # Reduced context lines from 5 to 3
    ))
    diff_text = "".join(char_diff)
    
    # Shorter, more focused prompt
    prompt = (
        "CODE COMPARISON - EXAMINE CHANGES:\n\n"
        "CHECKS:\n"
        "1. VARIABLE NAME TYPOS\n"
        "2. COMPILATION IMPACT\n"
        "3. BUSINESS IMPACT\n\n"
        
        "OUTPUT:\n"
        "**CHANGES:**\n"
        "- Line X: [change]\n\n"
        "**COMPILATION:** [CRITICAL/HIGH/MODERATE/LOW]\n"
        "**ACTION:** [recommendation]\n\n"
        
        f"ORIGINAL:\n{code1}\n\n"
        f"MODIFIED:\n{code2}\n\n"
        f"DIFF:\n{diff_text}"
    )

    summary = llm_analyze(prompt)
    mod_html = html_diff_highlight(code1, code2)
    
    return {
        "diff": diff_text, 
        "summary": summary, 
        "mod_highlight_html": mod_html
    }

def security_analysis(code):
    return {"details": "Removed Due to Optimization"}

def optimization_suggestions(code):
    """Optimized with shorter prompt"""
    prompt = (
    )

    resp = "Disabled due to"
    suggestions = re.findall(r"[•\-*]\s*.+", resp) or resp.splitlines()
    return {"details": "\n".join(suggestions)}

def review_for_production(code):
    return {"result": "Removed Due to Optimization"}

def extract_code_components(code):
    return {"details": "Removed for optimization"}

def run_code_testcase_compare(code1, code2, test_input=None):
    return {"summary": "Removed for optimization"}

def business_logic_impact(code1, code2):
    """Optimized with shorter prompt"""
    prompt = (
        "BUSINESS LOGIC IMPACT:\n\n"
        "EXAMINE:\n"
        "1. CALCULATIONS\n"
        "2. VARIABLE CHANGES\n"
        "3. VALIDATIONS\n\n"
        
        f"ORIGINAL:\n{code1}\n\n"
        f"MODIFIED:\n{code2}"
    )
    return {"impact": llm_analyze(prompt)}

def affected_test_cases(code1, code2):
    return {"test_cases": "Disabled Due to Optimization"}

def suggest_fix(code1, code2):
    return {"fix": "Disabled Due to Optimization"}

def generate_report(results, filename):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, "Oracle PL/SQL Analysis Report", ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(5)

    def section(title):
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, title, ln=True)
        pdf.ln(3)

    def write_text(text):
        pdf.set_font("Arial", "", 11)
        for line in (text or "").splitlines():
            pdf.multi_cell(0, 7, line)
        pdf.ln(5)

    sections = {
        "logical_diff": ("Logical Difference Analysis", "summary"),
        "logic": ("Logic Analysis", "summary"),
        "security": ("Security Audit", "details"),
       # "optimization": ("Optimization Suggestions", "details"),
        "review": ("Production Readiness", "result"),
        "components": ("Extracted Code Components", "details"),
        "runtime_test": ("Runtime Behavior Comparison", "summary"),
        "logic_impact": ("Business Logic Risk Analysis", "impact"),
        "test_case_diff": ("Test Case Impact", "test_cases"),
        "fix_suggestion": ("Fix Recommendation", "fix"),
    }

    for key, (title, field) in sections.items():
        if key in results:
            section(title)
            data = results[key]
            write_text(data.get(field, "No information available."))

    pdf.output(filename)
