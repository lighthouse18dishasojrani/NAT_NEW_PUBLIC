import subprocess
import re
import os
import json
from pathlib import Path

# Configuration
OLLAMA_MODEL = "llama3:8b"

def get_dataflow_steps(code: str) -> dict:
    """
    Enhanced dataflow step extraction that returns highly detailed structured data.
    """
    prompt = (
        "You are an expert PL/SQL code analyzer. Create a HIGHLY DETAILED flowchart structure.\n\n"
        
        "DETAILED ANALYSIS REQUIREMENTS:\n"
        "- Create 8-15 granular steps (not just high-level)\n"
        "- Include EVERY variable declaration and initialization\n"
        "- Show EACH SQL query as separate steps\n"
        "- Break down EVERY IF condition and CASE statement\n"
        "- Show individual calculations and assignments\n"
        "- Include exception handling blocks\n"
        "- Show cursor operations (OPEN, FETCH, CLOSE)\n"
        "- Include loop entry, iteration, and exit conditions\n"
        "- Show database operations (INSERT/UPDATE/DELETE) separately\n"
        "- Include function/procedure calls with parameters\n\n"
        
        "GRANULAR STEP EXAMPLES:\n"
        "- 'Declare variable L_COUNT as NUMBER'\n"
        "- 'Initialize L_TOTAL_AMT to 0'\n"
        "- 'Open cursor C_EMPLOYEE with parameter P_DEPT_ID'\n"
        "- 'Fetch employee record into L_EMP_REC'\n"
        "- 'Check IF L_EMP_REC.SALARY > 5000'\n"
        "- 'Calculate L_BONUS := L_EMP_REC.SALARY * 0.1'\n"
        "- 'Execute UPDATE employees SET bonus = L_BONUS'\n"
        "- 'Check for SQL exception in WHEN OTHERS block'\n\n"
        
        "Return EXACTLY this JSON structure with DETAILED steps:\n"
        "{\n"
        '  "nodes": [\n'
        '    {"id": 0, "label": "Start: Begin Procedure", "type": "start", "description": "Procedure execution begins"},\n'
        '    {"id": 1, "label": "Declare L_COUNT NUMBER", "type": "declare", "description": "Declare counter variable"},\n'
        '    {"id": 2, "label": "Initialize L_TOTAL := 0", "type": "assign", "description": "Set total amount to zero"},\n'
        '    {"id": 3, "label": "Open Cursor C_EMP", "type": "cursor", "description": "Open employee cursor"},\n'
        '    {"id": 4, "label": "Fetch Employee Record", "type": "fetch", "description": "Get next employee"},\n'
        '    {"id": 5, "label": "Check IF C_EMP%FOUND", "type": "condition", "description": "Test if record exists"},\n'
        '    {"id": 6, "label": "Calculate Salary * Rate", "type": "calculate", "description": "Compute bonus amount"},\n'
        '    {"id": 7, "label": "UPDATE Employee Bonus", "type": "dml", "description": "Save bonus to database"},\n'
        '    {"id": 8, "label": "Loop Back to Fetch", "type": "loop", "description": "Continue processing"},\n'
        '    {"id": 9, "label": "Close Cursor C_EMP", "type": "cursor", "description": "Clean up cursor"},\n'
        '    {"id": 10, "label": "COMMIT Transaction", "type": "transaction", "description": "Save changes"},\n'
        '    {"id": 11, "label": "Handle WHEN OTHERS", "type": "exception", "description": "Process any errors"},\n'
        '    {"id": 12, "label": "End: Return Success", "type": "end", "description": "Procedure completes"}\n'
        '  ],\n'
        '  "links": [\n'
        '    {"source": 0, "target": 1}, {"source": 1, "target": 2}, {"source": 2, "target": 3},\n'
        '    {"source": 3, "target": 4}, {"source": 4, "target": 5}, {"source": 5, "target": 6},\n'
        '    {"source": 6, "target": 7}, {"source": 7, "target": 8}, {"source": 8, "target": 4},\n'
        '    {"source": 5, "target": 9}, {"source": 9, "target": 10}, {"source": 10, "target": 12},\n'
        '    {"source": 11, "target": 12}\n'
        '  ]\n'
        '}\n\n'
        
        "CRITICAL INSTRUCTIONS:\n"
        "- Analyze EVERY line of code\n"
        "- Create separate nodes for variable declarations, assignments, SQL operations\n"
        "- Include decision points (IF/CASE) with true/false paths\n"
        "- Show loop structures with entry, body, and exit\n"
        "- Include exception handling paths\n"
        "- Return ONLY the JSON structure, no other text\n\n"
        
        f"PL/SQL Code to Analyze:\n{code}\n"
    )

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
            check=True
        )
        
        output = result.stdout.strip()
        print(f"Detailed LLM Output (first 300 chars): {output[:300]}...")
        
        flowchart_data = extract_json_from_output(output)
        
        if flowchart_data and validate_flowchart_data(flowchart_data):
            # Enhance with more detailed analysis if too few nodes
            if len(flowchart_data['nodes']) < 6:
                print("LLM output too simple, creating detailed fallback")
                return create_detailed_flowchart_data(code)
            return flowchart_data
        else:
            print("LLM output validation failed, using detailed fallback")
            return create_detailed_flowchart_data(code)
        
    except subprocess.TimeoutExpired:
        print("Ollama request timed out, using detailed fallback")
        return create_detailed_flowchart_data(code)
    except subprocess.CalledProcessError as e:
        print(f"Ollama error: {e}, using detailed fallback")
        return create_detailed_flowchart_data(code)
    except Exception as e:
        print(f"Unexpected error: {e}, using detailed fallback")
        return create_detailed_flowchart_data(code)

def extract_json_from_output(output: str) -> dict:
    """Extract JSON from LLM output using multiple strategies."""
    
    # Strategy 1: Try to parse entire output as JSON
    try:
        return json.loads(output.strip())
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Look for JSON between code blocks
    patterns = [
        r'``````',
        r'``````',
        r'\{.*?"nodes".*?\}',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, output, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # Strategy 3: Extract nodes and links separately
    try:
        nodes_match = re.search(r'"nodes":\s*\[(.*?)\]', output, re.DOTALL)
        links_match = re.search(r'"links":\s*\[(.*?)\]', output, re.DOTALL)
        
        if nodes_match and links_match:
            nodes_str = '[' + nodes_match.group(1) + ']'
            links_str = '[' + links_match.group(1) + ']'
            
            nodes = json.loads(nodes_str)
            links = json.loads(links_str)
            
            return {"nodes": nodes, "links": links}
    except:
        pass
    
    return None

def validate_flowchart_data(data):
    """Validate that flowchart data has required structure."""
    if not isinstance(data, dict):
        return False
    if 'nodes' not in data or 'links' not in data:
        return False
    if not isinstance(data['nodes'], list) or not isinstance(data['links'], list):
        return False
    if len(data['nodes']) < 3:
        return False
    
    # Validate and fix node structure
    for i, node in enumerate(data['nodes']):
        if not isinstance(node, dict):
            return False
        if 'id' not in node or 'label' not in node:
            return False
        # Ensure ID is consistent with position
        if node.get('id') != i:
            node['id'] = i
        # Add default type if missing
        if 'type' not in node:
            if i == 0:
                node['type'] = 'start'
            elif i == len(data['nodes']) - 1:
                node['type'] = 'end'
            else:
                node['type'] = 'process'
        # Add default description if missing
        if 'description' not in node:
            node['description'] = f"Processing step {i+1}"
    
    return True

def create_detailed_flowchart_data(code: str) -> dict:
    """
    Create extremely detailed flowchart data by analyzing PL/SQL code structure line by line.
    """
    nodes = []
    links = []
    node_id = 0
    
    # Always start with procedure entry
    nodes.append({
        "id": node_id,
        "label": "Start: Begin PL/SQL Block",
        "type": "start",
        "description": "Execution begins"
    })
    node_id += 1
    
    # Analyze code line by line for detailed breakdown
    lines = code.upper().strip().split('\n')
    code_lines = [line.strip() for line in lines if line.strip()]
    
    declare_section = False
    begin_section = False
    exception_section = False
    
    i = 0
    while i < len(code_lines):
        line = code_lines[i].strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('--') or line.startswith('/*'):
            i += 1
            continue
            
        # DECLARE section
        if line.startswith('DECLARE') or declare_section:
            declare_section = True
            if line.startswith('DECLARE'):
                nodes.append({
                    "id": node_id,
                    "label": "Enter Declaration Section",
                    "type": "declare",
                    "description": "Begin variable declarations"
                })
                node_id += 1
            elif any(keyword in line for keyword in ['NUMBER', 'VARCHAR2', 'DATE', 'BOOLEAN', 'CURSOR']):
                var_name = extract_variable_name(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Declare {var_name}",
                    "type": "declare",
                    "description": f"Declare variable: {line[:50]}..."
                })
                node_id += 1
            elif line.startswith('BEGIN'):
                declare_section = False
                begin_section = True
                nodes.append({
                    "id": node_id,
                    "label": "Begin Execution Block",
                    "type": "begin",
                    "description": "Start main logic execution"
                })
                node_id += 1
        
        # Main execution block
        elif begin_section and not exception_section:
            if 'SELECT' in line:
                nodes.append({
                    "id": node_id,
                    "label": f"Execute SELECT Query",
                    "type": "query",
                    "description": f"Database query: {line[:50]}..."
                })
                node_id += 1
                
            elif 'INSERT' in line:
                nodes.append({
                    "id": node_id,
                    "label": f"Execute INSERT Statement",
                    "type": "dml",
                    "description": f"Insert data: {line[:50]}..."
                })
                node_id += 1
                
            elif 'UPDATE' in line:
                nodes.append({
                    "id": node_id,
                    "label": f"Execute UPDATE Statement",
                    "type": "dml",
                    "description": f"Update data: {line[:50]}..."
                })
                node_id += 1
                
            elif 'DELETE' in line:
                nodes.append({
                    "id": node_id,
                    "label": f"Execute DELETE Statement",
                    "type": "dml",
                    "description": f"Delete data: {line[:50]}..."
                })
                node_id += 1
                
            elif ':=' in line:
                var_name = line.split(':=')[0].strip()
                nodes.append({
                    "id": node_id,
                    "label": f"Assign {var_name}",
                    "type": "assign",
                    "description": f"Variable assignment: {line[:50]}..."
                })
                node_id += 1
                
            elif line.startswith('IF'):
                condition = extract_condition(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Check IF {condition}",
                    "type": "condition",
                    "description": f"Conditional check: {line[:50]}..."
                })
                node_id += 1
                
            elif line.startswith('CASE'):
                nodes.append({
                    "id": node_id,
                    "label": "Evaluate CASE Statement",
                    "type": "condition",
                    "description": f"Case evaluation: {line[:50]}..."
                })
                node_id += 1
                
            elif line.startswith('FOR') or line.startswith('WHILE'):
                loop_var = extract_loop_variable(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Enter Loop: {loop_var}",
                    "type": "loop_start",
                    "description": f"Loop initiation: {line[:50]}..."
                })
                node_id += 1
                
            elif 'LOOP' in line and not line.startswith('FOR'):
                nodes.append({
                    "id": node_id,
                    "label": "Begin Loop Block",
                    "type": "loop_start",
                    "description": "Start loop execution"
                })
                node_id += 1
                
            elif line.startswith('END LOOP'):
                nodes.append({
                    "id": node_id,
                    "label": "End Loop - Check Condition",
                    "type": "loop_end",
                    "description": "Loop iteration complete, check continue condition"
                })
                node_id += 1
                
            elif 'OPEN' in line and 'CURSOR' in line:
                cursor_name = extract_cursor_name(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Open Cursor {cursor_name}",
                    "type": "cursor",
                    "description": f"Open cursor for data retrieval"
                })
                node_id += 1
                
            elif 'FETCH' in line:
                cursor_name = extract_cursor_name(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Fetch from {cursor_name}",
                    "type": "fetch",
                    "description": "Retrieve next record from cursor"
                })
                node_id += 1
                
            elif 'CLOSE' in line and 'CURSOR' in line:
                cursor_name = extract_cursor_name(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Close Cursor {cursor_name}",
                    "type": "cursor",
                    "description": "Clean up cursor resources"
                })
                node_id += 1
                
            elif 'COMMIT' in line:
                nodes.append({
                    "id": node_id,
                    "label": "COMMIT Transaction",
                    "type": "transaction",
                    "description": "Save all changes to database"
                })
                node_id += 1
                
            elif 'ROLLBACK' in line:
                nodes.append({
                    "id": node_id,
                    "label": "ROLLBACK Transaction",
                    "type": "transaction",
                    "description": "Undo all changes"
                })
                node_id += 1
                
            elif line.startswith('EXCEPTION'):
                exception_section = True
                nodes.append({
                    "id": node_id,
                    "label": "Enter Exception Handler",
                    "type": "exception",
                    "description": "Handle runtime exceptions"
                })
                node_id += 1
        
        # Exception handling section
        elif exception_section:
            if 'WHEN' in line:
                exception_type = extract_exception_type(line)
                nodes.append({
                    "id": node_id,
                    "label": f"Handle {exception_type}",
                    "type": "exception",
                    "description": f"Process {exception_type} exception"
                })
                node_id += 1
                
            elif line.startswith('END'):
                break
        
        i += 1
    
    # Always end with procedure exit
    nodes.append({
        "id": node_id,
        "label": "End: Complete Execution",
        "type": "end",
        "description": "PL/SQL block execution complete"
    })
    
    # Create sequential links between all nodes
    for i in range(len(nodes) - 1):
        links.append({"source": i, "target": i + 1})
    
    # Add some conditional branches for IF statements and loops
    add_conditional_links(nodes, links)
    
    return {"nodes": nodes, "links": links}

def extract_variable_name(line):
    """Extract variable name from declaration line."""
    words = line.split()
    for i, word in enumerate(words):
        if word in ['NUMBER', 'VARCHAR2', 'DATE', 'BOOLEAN', 'INTEGER']:
            if i > 0:
                return words[i-1]
    return "VARIABLE"

def extract_condition(line):
    """Extract condition from IF statement."""
    if_pos = line.find('IF')
    then_pos = line.find('THEN')
    if if_pos != -1 and then_pos != -1:
        return line[if_pos+2:then_pos].strip()
    return "CONDITION"

def extract_loop_variable(line):
    """Extract loop variable from FOR loop."""
    words = line.split()
    if 'FOR' in words:
        idx = words.index('FOR')
        if idx + 1 < len(words):
            return words[idx + 1]
    return "LOOP_VAR"

def extract_cursor_name(line):
    """Extract cursor name from cursor operations."""
    words = line.split()
    for word in words:
        if word.startswith('C_') or word.endswith('_CURSOR') or word.startswith('CUR_'):
            return word
    return "CURSOR"

def extract_exception_type(line):
    """Extract exception type from WHEN clause."""
    when_pos = line.find('WHEN')
    then_pos = line.find('THEN')
    if when_pos != -1:
        if then_pos != -1:
            return line[when_pos+4:then_pos].strip()
        else:
            return line[when_pos+4:].strip()
    return "EXCEPTION"

def add_conditional_links(nodes, links):
    """Add conditional branching links for decision points."""
    for i, node in enumerate(nodes):
        if node['type'] == 'condition':
            # Add alternative path for false condition
            if i + 2 < len(nodes):
                # Skip next node and link to the one after (false branch)
                links.append({"source": i, "target": i + 2, "condition": "false"})
        elif node['type'] == 'loop_end':
            # Add loop back link
            loop_start = find_loop_start(nodes, i)
            if loop_start != -1:
                links.append({"source": i, "target": loop_start, "condition": "continue"})

def find_loop_start(nodes, current_pos):
    """Find the corresponding loop start for a loop end."""
    for i in range(current_pos - 1, -1, -1):
        if nodes[i]['type'] in ['loop_start', 'loop']:
            return i
    return -1

def generate_flowchart(steps, filename="flowchart"):
    """
    Legacy function for backward compatibility - creates static image.
    """
    try:
        import graphviz
        
        chart = graphviz.Digraph(format="png")
        chart.attr(rankdir='TB')
        chart.attr('node', shape='box', style='filled', color='lightblue')
        chart.attr('edge', color='darkblue', arrowhead='vee')
        
        for idx, step in enumerate(steps):
            display_text = step if len(step) <= 50 else step[:47] + "..."
            chart.node(f"step{idx}", display_text)
        
        for idx in range(len(steps) - 1):
            chart.edge(f"step{idx}", f"step{idx + 1}")
        
        output_path = f"{filename}_{hash(' '.join(steps)) % 10000}"
        chart_file = chart.render(output_path, cleanup=True)
        
        return chart_file
        
    except ImportError:
        print("Graphviz not available for static chart generation")
        return None
    except Exception as e:
        print(f"Static flowchart generation failed: {e}")
        return None

# Command-line usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Highly Detailed PL/SQL Flowchart")
    parser.add_argument("infile", help="Input PL/SQL file")
    parser.add_argument("--outfile", default="detailed_plsql_flowchart", help="Output file base name")
    parser.add_argument("--format", choices=["json", "static"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.infile):
        print(f"File not found: {args.infile}")
        exit(1)
    
    try:
        with open(args.infile, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        
        if args.format == "json":
            flowchart_data = get_dataflow_steps(code)
            
            if not flowchart_data or not flowchart_data.get('nodes'):
                print("No flowchart data could be extracted.")
                exit(2)
            
            # Save as JSON for web interface
            output_file = f"{args.outfile}.json"
            with open(output_file, 'w') as f:
                json.dump(flowchart_data, f, indent=2)
            
            print(f"Detailed interactive flowchart data generated: {output_file}")
            print(f"Nodes: {len(flowchart_data['nodes'])}")
            print(f"Links: {len(flowchart_data['links'])}")
            print(f"Node types: {set(node.get('type', 'unknown') for node in flowchart_data['nodes'])}")
        
        else:  # static format
            # Convert to simple steps for static generation
            flowchart_data = get_dataflow_steps(code)
            if flowchart_data and flowchart_data.get('nodes'):
                steps = [node['label'] for node in flowchart_data['nodes']]
                outfile = generate_flowchart(steps, filename=args.outfile)
                if outfile:
                    print(f"Static flowchart generated: {outfile}")
                else:
                    print("Static flowchart generation failed")
            else:
                print("No data available for static flowchart")
            
    except Exception as e:
        print(f"Error: {e}")
        exit(4)
