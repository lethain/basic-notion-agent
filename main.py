import json
import os
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional


def lambda_handler(event: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    AWS Lambda handler for Notion webhook processing.
    
    Args:
        event: Lambda event containing query parameters and request body
        context: Lambda context (unused)
        
    Returns:
        JSON string with processing metadata
    """
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        # Check client token if configured
        env_client_token = os.environ.get('client_token')
        if env_client_token:
            provided_token = query_params.get('client_token')
            if not provided_token or provided_token != env_client_token:
                return json.dumps({"error": "Invalid client token", 'event': event})
            
        # Get prompt_id and retrieve prompt page
        prompt_id = query_params.get('prompt_id')
        if not prompt_id:
            return json.dumps({"error": "Missing prompt_id parameter", 'event': event})
        
        prompt_page = get_page(prompt_id)

        print(prompt_page['markdown'])
        
        # Get changed page ID from request body
        event_body = event.get('body', '')
        request_data = json.loads(event_body).get('data')
        changed_page_id = request_data.get('id')
        
        if not changed_page_id:
            return json.dumps({"error": "Missing page ID in request data", 'event': event})
        
        changed_page = get_page(changed_page_id)
        print(changed_page['markdown'])
        
        result = {
            "prompt_page": prompt_page,
            "changed_page": changed_page,
            "request_id": request_data.get('request_id')
        }
        
        return json.dumps(result)
        
    except Exception as e:
        return json.dumps({"error": str(e), 'event': event})


def get_page(page_id: str) -> Dict[str, Any]:
    """
    Retrieve a Notion page and convert it to markdown format.
    
    Args:
        page_id: The Notion page ID to retrieve
        
    Returns:
        Dictionary containing page_id and markdown content with block_ids
    """
    notion_token = os.environ.get('NOTION_TOKEN')
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable is required")
    
    blocks = []
    start_cursor = None
    has_more = True
    
    while has_more:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        if start_cursor:
            url += f"?start_cursor={start_cursor}"
        
        req = urllib.request.Request(
            url,
            headers={
                'Authorization': f'Bearer {notion_token}',
                'Notion-Version': '2022-06-28',
                'Content-Type': 'application/json'
            }
        )

        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        blocks.extend(data.get('results', []))
        has_more = data.get('has_more', False)
        start_cursor = data.get('next_cursor')
    
    markdown_content = notion_to_markdown(blocks)
    
    return {
        "page_id": page_id,
        "markdown": markdown_content
    }


def notion_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    """
    Convert Notion blocks to Markdown format while preserving block IDs.
    
    Args:
        blocks: List of Notion block objects
        
    Returns:
        Markdown string with block_id annotations
    """
    markdown_lines = []
    
    for block in blocks:
        block_id = block.get('id', '')
        block_type = block.get('type', '')
        
        if block_type == 'paragraph':
            content = _extract_rich_text(block.get('paragraph', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(content)
                markdown_lines.append("")
        
        elif block_type.startswith('heading_'):
            level = int(block_type.split('_')[1])
            content = _extract_rich_text(block.get(block_type, {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"{'#' * level} {content}")
                markdown_lines.append("")
        
        elif block_type == 'bulleted_list_item':
            content = _extract_rich_text(block.get('bulleted_list_item', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"- {content}")
                markdown_lines.append("")
        
        elif block_type == 'numbered_list_item':
            content = _extract_rich_text(block.get('numbered_list_item', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"1. {content}")
                markdown_lines.append("")
        
        elif block_type == 'code':
            code_block = block.get('code', {})
            content = _extract_rich_text(code_block.get('rich_text', []))
            language = code_block.get('language', '')
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"```{language}")
                markdown_lines.append(content)
                markdown_lines.append("```")
                markdown_lines.append("")
        
        elif block_type == 'quote':
            content = _extract_rich_text(block.get('quote', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"> {content}")
                markdown_lines.append("")
    
    return "\n".join(markdown_lines).strip()


def _extract_rich_text(rich_text: List[Dict[str, Any]]) -> str:
    """
    Extract plain text from Notion rich text objects with formatting.
    
    Args:
        rich_text: List of Notion rich text objects
        
    Returns:
        Formatted markdown string
    """
    result = []
    
    for text_obj in rich_text:
        content = text_obj.get('plain_text', '')
        annotations = text_obj.get('annotations', {})
        href = text_obj.get('href')
        
        # Apply formatting
        if annotations.get('bold'):
            content = f"**{content}**"
        if annotations.get('italic'):
            content = f"*{content}*"
        if annotations.get('strikethrough'):
            content = f"~~{content}~~"
        if annotations.get('code'):
            content = f"`{content}`"
        
        # Handle links
        if href:
            content = f"[{content}]({href})"
        
        result.append(content)
    
    return "".join(result)


def markdown_to_notion(markdown: str) -> List[Dict[str, Any]]:
    """
    Convert Markdown text to Notion blocks format.
    
    Args:
        markdown: Markdown string to convert
        
    Returns:
        List of Notion block objects
    """
    blocks = []
    lines = markdown.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Handle headers
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            content = line.lstrip('# ').strip()
            blocks.append({
                "object": "block",
                "type": f"heading_{level}",
                f"heading_{level}": {
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "color": "default"
                }
            })
        
        # Handle code blocks
        elif line.startswith('```'):
            language = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": language
                }
            })
        
        # Handle bullet points
        elif line.startswith('- '):
            content = line[2:].strip()
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "color": "default"
                }
            })
        
        # Handle numbered lists
        elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
            content = line[3:].strip()
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "color": "default"
                }
            })
        
        # Handle quotes
        elif line.startswith('> '):
            content = line[2:].strip()
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "color": "default"
                }
            })
        
        # Handle regular paragraphs
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}],
                    "color": "default"
                }
            })
        
        i += 1
    
    return blocks


if __name__ == "__main__":
    with open('messages/automation_webhook.json', 'r') as fin:
        
        event = {
            'body': fin.read(),
            'queryStringParameters': {
                'prompt_id': '236ac777210d80029121fc57a4ad7a0a',
            }
        }
        context = {}
        resp = lambda_handler(event, context)
        print(resp)
    

