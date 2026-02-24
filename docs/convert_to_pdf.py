#!/usr/bin/env python3
"""
Convert stepBystepExpansion.md to PDF with rendered Mermaid diagrams.

Pipeline:
1. Extract mermaid code blocks → render to PNG via mmdc
2. Replace mermaid blocks with image references
3. Convert modified markdown → HTML via pandoc
4. Convert HTML → PDF via puppeteer (Node.js)
"""

import os
import re
import subprocess
import sys
import tempfile
import shutil
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "stepBystepExpansion.md")
OUTPUT_PDF = os.path.join(SCRIPT_DIR, "stepBystepExpansion.pdf")

def check_dependencies():
    """Check that required tools are available."""
    for cmd in ["mmdc", "pandoc", "node"]:
        if not shutil.which(cmd):
            print(f"ERROR: '{cmd}' not found in PATH. Please install it.")
            sys.exit(1)

def extract_and_render_mermaid(md_content, tmpdir):
    """Extract mermaid code blocks, render to PNG, return modified markdown."""
    pattern = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)
    matches = list(pattern.finditer(md_content))
    
    if not matches:
        print("No mermaid blocks found.")
        return md_content
    
    print(f"Found {len(matches)} mermaid diagrams. Rendering...")
    
    # mmdc config for better rendering
    mmdc_config = {
        "theme": "default",
        "themeVariables": {
            "fontSize": "14px"
        }
    }
    config_path = os.path.join(tmpdir, "mermaid-config.json")
    with open(config_path, 'w') as f:
        json.dump(mmdc_config, f)
    
    # CSS for puppeteer to ensure wider rendering
    css_path = os.path.join(tmpdir, "mermaid.css")
    with open(css_path, 'w') as f:
        f.write("body { font-family: Arial, sans-serif; }")

    result = md_content
    offset = 0
    
    for i, match in enumerate(matches):
        mermaid_code = match.group(1).strip()
        mmd_file = os.path.join(tmpdir, f"diagram_{i}.mmd")
        png_file = os.path.join(tmpdir, f"diagram_{i}.png")
        
        with open(mmd_file, 'w') as f:
            f.write(mermaid_code)
        
        print(f"  Rendering diagram {i+1}/{len(matches)}...", end=" ", flush=True)
        
        try:
            proc = subprocess.run(
                [
                    "mmdc",
                    "-i", mmd_file,
                    "-o", png_file,
                    "-b", "white",
                    "-w", "1200",
                    "-s", "2",
                    "-c", config_path,
                ],
                capture_output=True, text=True, timeout=60
            )
            if proc.returncode != 0:
                print(f"WARN (exit {proc.returncode})")
                if proc.stderr:
                    print(f"    stderr: {proc.stderr[:200]}")
                # Keep the mermaid code block if rendering fails
                continue
            
            if not os.path.exists(png_file):
                print("WARN (no output file)")
                continue
                
            print("OK")
            
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            continue
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        
        # Replace the mermaid block with an image reference
        old = match.group(0)
        new = f'![Diagram {i+1}]({png_file})'
        
        start = match.start() + offset
        end = match.end() + offset
        result = result[:start] + new + result[end:]
        offset += len(new) - len(old)
    
    return result

def markdown_to_html(md_content, tmpdir):
    """Convert modified markdown to standalone HTML via pandoc."""
    md_file = os.path.join(tmpdir, "processed.md")
    html_file = os.path.join(tmpdir, "output.html")
    
    with open(md_file, 'w') as f:
        f.write(md_content)
    
    # Custom CSS for nice PDF styling
    css_content = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        max-width: 900px;
        margin: 0 auto;
        padding: 40px 30px;
        color: #1a1a1a;
        line-height: 1.6;
        font-size: 11pt;
    }
    h1 {
        color: #1a1a1a;
        border-bottom: 2px solid #333;
        padding-bottom: 8px;
        margin-top: 2.5em;
        font-size: 1.6em;
        page-break-before: always;
    }
    h1:first-of-type {
        page-break-before: avoid;
    }
    h2, h3 {
        color: #2c3e50;
        margin-top: 1.5em;
    }
    h3 {
        font-size: 1.1em;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
        font-size: 0.9em;
    }
    th, td {
        border: 1px solid #ccc;
        padding: 6px 10px;
        text-align: left;
    }
    th {
        background-color: #f0f0f0;
        font-weight: 600;
    }
    tr:nth-child(even) {
        background-color: #fafafa;
    }
    code {
        background-color: #f4f4f4;
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 0.9em;
    }
    pre {
        background-color: #f4f4f4;
        padding: 12px;
        border-radius: 5px;
        overflow-x: auto;
        font-size: 0.85em;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1.5em auto;
    }
    blockquote {
        border-left: 3px solid #ccc;
        padding-left: 15px;
        color: #555;
        margin: 1em 0;
    }
    hr {
        border: none;
        border-top: 1px solid #ddd;
        margin: 2em 0;
    }
    a {
        color: #2563eb;
        text-decoration: none;
    }
    @media print {
        body { margin: 0; padding: 20px; }
        h1 { page-break-before: always; }
        h1:first-of-type { page-break-before: avoid; }
        table, img { page-break-inside: avoid; }
    }
    """
    
    css_file = os.path.join(tmpdir, "style.css")
    with open(css_file, 'w') as f:
        f.write(css_content)
    
    print("Converting markdown to HTML via pandoc...")
    proc = subprocess.run(
        [
            "pandoc",
            md_file,
            "-o", html_file,
            "--standalone",
            "--css", css_file,
            "--embed-resources",
            "--metadata", "title=Drop Ceiling — Step-by-Step Complexity Expansion",
        ],
        capture_output=True, text=True
    )
    
    if proc.returncode != 0:
        print(f"Pandoc error: {proc.stderr}")
        sys.exit(1)
    
    print("HTML generated.")
    return html_file

def html_to_pdf(html_file, output_pdf):
    """Convert HTML to PDF using puppeteer via a small Node.js script."""
    
    # Find puppeteer from mermaid-cli's dependencies
    node_script = f"""
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }});
    const page = await browser.newPage();
    
    const htmlPath = {json.dumps(html_file)};
    const pdfPath = {json.dumps(output_pdf)};
    
    await page.goto('file://' + htmlPath, {{ waitUntil: 'networkidle0' }});
    
    await page.pdf({{
        path: pdfPath,
        format: 'Letter',
        margin: {{
            top: '0.75in',
            bottom: '0.75in',
            left: '0.75in',
            right: '0.75in'
        }},
        printBackground: true,
        displayHeaderFooter: false,
    }});
    
    await browser.close();
    console.log('PDF generated: ' + pdfPath);
}})();
"""
    
    # Try to find puppeteer
    # It should be available from mermaid-cli's node_modules
    puppeteer_paths = [
        # Global npm
        os.path.expanduser("~/.npm-global/lib/node_modules/puppeteer"),
        "/opt/homebrew/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer",
        "/opt/homebrew/lib/node_modules/puppeteer",
    ]
    
    # Also search for it dynamically
    try:
        result = subprocess.run(
            ["node", "-e", "console.log(require.resolve('puppeteer'))"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            puppeteer_paths.insert(0, os.path.dirname(result.stdout.strip()))
    except:
        pass
    
    print("Converting HTML to PDF via puppeteer...")
    
    # Write the Node script to a temp file
    script_dir = os.path.dirname(html_file)
    script_file = os.path.join(script_dir, "html_to_pdf.js")
    with open(script_file, 'w') as f:
        f.write(node_script)
    
    # Try running with global resolution first
    proc = subprocess.run(
        ["node", script_file],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "NODE_PATH": "/opt/homebrew/lib/node_modules:/opt/homebrew/lib/node_modules/@mermaid-js/mermaid-cli/node_modules"}
    )
    
    if proc.returncode != 0:
        print(f"Node.js error: {proc.stderr[:500]}")
        # Fallback: try npx
        print("Trying alternative approach...")
        return False
    
    print(proc.stdout.strip())
    return True

def main():
    check_dependencies()
    
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_PDF}")
    print()
    
    with open(INPUT_FILE, 'r') as f:
        md_content = f.read()
    
    with tempfile.TemporaryDirectory(prefix="md2pdf_") as tmpdir:
        print(f"Working directory: {tmpdir}\n")
        
        # Step 1: Render mermaid diagrams
        processed_md = extract_and_render_mermaid(md_content, tmpdir)
        
        # Step 2: Convert to HTML
        html_file = markdown_to_html(processed_md, tmpdir)
        
        # Step 3: Convert HTML to PDF
        success = html_to_pdf(html_file, OUTPUT_PDF)
        
        if not success:
            # Fallback: copy HTML and try alternative PDF generation
            fallback_html = OUTPUT_PDF.replace('.pdf', '.html')
            shutil.copy2(html_file, fallback_html)
            print(f"\nFallback: HTML saved to {fallback_html}")
            print("You can open it in a browser and Print → Save as PDF")
            return
    
    if os.path.exists(OUTPUT_PDF):
        size_kb = os.path.getsize(OUTPUT_PDF) / 1024
        print(f"\nSuccess! PDF generated: {OUTPUT_PDF} ({size_kb:.0f} KB)")
    else:
        print("\nERROR: PDF was not generated.")
        sys.exit(1)

if __name__ == "__main__":
    main()
