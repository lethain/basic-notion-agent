import json
import os
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional
from openai import OpenAI


def lambda_handler(event: Dict[str, Any], context: Dict[str, Any], debug: bool=False) -> str:
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
        prompt_name = prompt_page['name']

        if debug:
            prompt_str = "# " + prompt_name + "\n\n" + prompt_page['markdown']
            open('prompt.txt', 'w').write(prompt_str)
        
        # Get changed page ID from request body
        event_body = event.get('body', '')
        request_data = json.loads(event_body).get('data')
        changed_page_id = request_data.get('id')
        
        if not changed_page_id:
            return json.dumps({"error": "Missing page ID in request data", 'event': event})

        changed_page = get_page(changed_page_id)
        changed_name = changed_page['name']

        if debug:
            changed_str = "# " + changed_name + "\n\n" + changed_page['markdown']
            open('changed.txt', 'w').write(changed_str)            
        
        # Get model from query parameters, default to gpt-4o
        model = query_params.get('model', 'gpt-4o')
        
        # Query OpenAI using prompt page as system prompt and changed page as user prompt
        openai_response = query_openai(
            system_prompt=prompt_page['markdown'],
            user_prompt=changed_page['markdown'], 
            model=model,
            page_id=changed_page_id,
            commenter_name=prompt_name
        )
        
        result = {
            "openai_response": openai_response,
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
        Dictionary containing page_id, title, and markdown content with block_ids
    """
    notion_token = os.environ.get('NOTION_TOKEN')
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable is required")
    
    # Initialize user cache for this page retrieval
    user_cache = {}
    
    # First, get the page metadata to extract the title
    page_url = f"https://api.notion.com/v1/pages/{page_id}"
    page_req = urllib.request.Request(
        page_url,
        headers={
            'Authorization': f'Bearer {notion_token}',
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json'
        }
    )
    
    with urllib.request.urlopen(page_req) as response:
        page_data = json.loads(response.read().decode())
    
    # Extract the title from properties
    page_title = extract_page_title(page_data.get('properties', {}))
    
    # Now get the page blocks
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

    markdown_content = notion_to_markdown(blocks, notion_token, user_cache)
    
    return {
        "page_id": page_id,
        "name": page_title,
        "markdown": markdown_content
    }


def notion_to_markdown(blocks: List[Dict[str, Any]], notion_token: str, user_cache: Dict[str, Dict[str, Any]]) -> str:
    """
    Convert Notion blocks to Markdown format while preserving block IDs and including comments.
    
    Args:
        blocks: List of Notion block objects
        notion_token: Notion API token for retrieving comments
        user_cache: Dictionary to cache user information
        
    Returns:
        Markdown string with block_id annotations and comments
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
                # Add comments for this block
                _add_block_comments(markdown_lines, block_id, notion_token, user_cache)
                markdown_lines.append("")
        
        elif block_type.startswith('heading_'):
            level = int(block_type.split('_')[1])
            content = _extract_rich_text(block.get(block_type, {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"{'#' * level} {content}")
                # Add comments for this block
                _add_block_comments(markdown_lines, block_id, notion_token, user_cache)
                markdown_lines.append("")
        
        elif block_type == 'bulleted_list_item':
            content = _extract_rich_text(block.get('bulleted_list_item', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"- {content}")
                # Add comments for this block
                _add_block_comments(markdown_lines, block_id, notion_token, user_cache)
                markdown_lines.append("")
        
        elif block_type == 'numbered_list_item':
            content = _extract_rich_text(block.get('numbered_list_item', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"1. {content}")
                # Add comments for this block
                _add_block_comments(markdown_lines, block_id, notion_token, user_cache)
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
                # Add comments for this block
                _add_block_comments(markdown_lines, block_id, notion_token, user_cache)
                markdown_lines.append("")
        
        elif block_type == 'quote':
            content = _extract_rich_text(block.get('quote', {}).get('rich_text', []))
            if content.strip():
                markdown_lines.append(f"block_id: {block_id}")
                markdown_lines.append(f"> {content}")
                # Add comments for this block
                _add_block_comments(markdown_lines, block_id, notion_token, user_cache)
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


def get_user(user_id: str, notion_token: str, user_cache: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Retrieve user information from Notion API with caching.
    
    Args:
        user_id: The Notion user ID
        notion_token: Notion API token
        user_cache: Cache to store user information
        
    Returns:
        Dictionary with user information
    """
    # Check cache first
    if user_id in user_cache:
        return user_cache[user_id]
    
    # Fetch from API
    url = f"https://api.notion.com/v1/users/{user_id}"
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Bearer {notion_token}',
            'Notion-Version': '2022-06-28'
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            user_data = json.loads(response.read().decode())
        
        # Extract relevant information
        user_info = {
            'name': user_data.get('name', 'Unknown User'),
            'email': '',
            'id': user_id
        }
        
        # Get email if it's a person type user
        if user_data.get('type') == 'person' and 'person' in user_data:
            user_info['email'] = user_data['person'].get('email', '')
        
        # Cache the result
        user_cache[user_id] = user_info
        return user_info
        
    except urllib.error.HTTPError as e:
        # If user API fails, return basic info
        fallback_info = {
            'name': 'Unknown User',
            'email': '',
            'id': user_id
        }
        user_cache[user_id] = fallback_info
        return fallback_info
    except Exception as e:
        # For any other error, return basic info
        fallback_info = {
            'name': 'Unknown User',
            'email': '',
            'id': user_id
        }
        user_cache[user_id] = fallback_info
        return fallback_info


def _add_block_comments(markdown_lines: List[str], block_id: str, notion_token: str, user_cache: Dict[str, Dict[str, Any]]) -> None:
    """
    Add comments for a specific block to the markdown lines.
    
    Args:
        markdown_lines: List to append comment lines to
        block_id: The block ID to get comments for
        notion_token: Notion API token
        user_cache: Cache for user information
    """
    comments = get_block_comments(block_id, notion_token)
    
    for comment in comments:
        comment_id = comment.get('id', '')
        comment_text = _extract_rich_text(comment.get('rich_text', []))
        user_id = comment.get('created_by', {}).get('id', '')
        created_time = comment.get('created_time', '')
        
        # Get user information
        if user_id:
            user_info = get_user(user_id, notion_token, user_cache)
            user_name = user_info['name']
            user_email = user_info['email']
            
            # Format: **Comment by "Real name" "email address" (UserID) at $time:**
            email_part = f' "{user_email}"' if user_email else ''
            comment_by = f'**Comment by "{user_name}"{email_part} ({user_id}) at {created_time}:**'
        else:
            comment_by = f'**Comment by Unknown User at {created_time}:**'
        
        markdown_lines.append(f"comment block id: {comment_id}")
        markdown_lines.append(comment_by)
        markdown_lines.append(comment_text)


def get_block_comments(block_id: str, notion_token: str) -> List[Dict[str, Any]]:
    """
    Retrieve all comments associated with a specific Notion block.
    
    Args:
        block_id: The Notion block ID
        notion_token: The Notion API token
        
    Returns:
        List of comment objects
    """
    comments = []
    start_cursor = None
    has_more = True
    
    while has_more:
        url = f"https://api.notion.com/v1/comments?block_id={block_id}"
        if start_cursor:
            url += f"&start_cursor={start_cursor}"
        
        req = urllib.request.Request(
            url,
            headers={
                'Authorization': f'Bearer {notion_token}',
                'Notion-Version': '2022-06-28'
            }
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
            
            comments.extend(data.get('results', []))
            has_more = data.get('has_more', False)
            start_cursor = data.get('next_cursor')
            
        except urllib.error.HTTPError as e:
            # If comments API fails (e.g. permissions), return empty list
            if e.code == 404 or e.code == 403:
                break
            else:
                raise e
    
    return comments


def extract_page_title(properties: Dict[str, Any]) -> str:
    """
    Extract the plain text title from Notion page properties.
    
    Args:
        properties: The properties object from a Notion page
        
    Returns:
        Plain text title string
    """
    # Look for the title property (usually has id "title" or type "title")
    for prop_name, prop_data in properties.items():
        if prop_data.get('type') == 'title':
            title_array = prop_data.get('title', [])
            if title_array:
                # Extract plain text from rich text objects
                title_parts = []
                for text_obj in title_array:
                    title_parts.append(text_obj.get('plain_text', ''))
                return ''.join(title_parts)
    
    # Fallback: look for a property named "Name" or "Title"
    for prop_name in ['Name', 'Title', 'name', 'title']:
        if prop_name in properties:
            prop_data = properties[prop_name]
            if prop_data.get('type') == 'title':
                title_array = prop_data.get('title', [])
                if title_array:
                    title_parts = []
                    for text_obj in title_array:
                        title_parts.append(text_obj.get('plain_text', ''))
                    return ''.join(title_parts)
    
    # Final fallback
    return 'Untitled'




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


def notion_comment(block_id: str, comment_markdown: str, commenter_name: str) -> Dict[str, Any]:
    """
    Add a comment to a specific block in Notion.
    
    Args:
        block_id: The ID of the block to comment on
        comment_markdown: The comment content in Markdown format
        
    Returns:
        Dictionary with comment creation result
    """
    print('notion_comment', block_id, comment_markdown)
    
    notion_token = os.environ.get('NOTION_TOKEN')
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable is required")
    
    # Convert markdown to notion rich text format
    comment_blocks = markdown_to_notion(comment_markdown)
    
    # Extract rich text from the first block (comments are single rich text arrays)
    if not comment_blocks:
        raise ValueError("Comment markdown could not be converted to Notion blocks")
    
    # Get rich text from the first block
    rich_text = [{"type": "text", "text": {"content": comment_markdown}}]
    
    # Prepare comment data
    comment_data = {
        "parent": {
            "block_id": block_id
        },
        "rich_text": rich_text,
    }
    if commenter_name:
        comment_data['display_name'] = {
            "type": "custom",
            "custom": {
                "name": commenter_name
            }
        }
    
    # Make API request
    url = "https://api.notion.com/v1/comments"
    req_data = json.dumps(comment_data).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=req_data,
        method='POST',
        headers={
            'Authorization': f'Bearer {notion_token}',
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json'
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return {"success": True, "comment_id": result.get('id'), "result": result}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def query_openai(system_prompt: str, user_prompt: str, model: str, page_id: str, commenter_name: str) -> str:
    """
    Query OpenAI API with system and user prompts, including function calling capability.
    
    Args:
        system_prompt: System prompt (from prompt page)
        user_prompt: User prompt (from changed page)
        model: OpenAI model to use
        
    Returns:
        OpenAI response text
    """
    openai_api_key = os.environ.get('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    client = OpenAI(api_key=openai_api_key)
    
    # Define the notion_comment tool for OpenAI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "notion_comment",
                "description": "Add a comment to a specific block in the Notion document",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "block_id": {
                            "type": "string",
                            "description": "The ID of the block to comment on (found in the block_id lines in the document)"
                        },
                        "comment_markdown": {
                            "type": "string", 
                            "description": "The comment content in Markdown format"
                        }
                    },
                    "required": ["block_id", "comment_markdown"]
                }
            }
        }
    ]
    
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # Check if the model wants to call functions
        if response_message.tool_calls:
            # Process function calls
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "notion_comment":
                    # Parse function arguments
                    function_args = json.loads(tool_call.function.arguments)
                    block_id = function_args.get("block_id")
                    comment_markdown = function_args.get("comment_markdown")
                    
                    # Call the notion_comment function
                    comment_result = notion_comment(block_id, comment_markdown, commenter_name)
                    
                    # Add the function result to messages
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "notion_comment",
                        "content": json.dumps(comment_result)
                    })
            
            # Get final response after function calls
            final_response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            notion_comment(page_id, final_response.choices[0].message.content, commenter_name)

        else:
            # No function calls, return regular response
            return response_message.content
        
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


if __name__ == "__main__":
    with open('messages/automation_webhook.json', 'r') as fin:
        with open('test.json', 'r') as test_in:
            test_envs = json.loads(test_in.read())
        
        for key, val in test_envs.items():
            os.environ[key] = val
        
        event = {
            'body': fin.read(),
            'queryStringParameters': {
                'prompt_id': test_envs['PROMPT_ID'],
            }
        }
        event['data']['id'] = test_envs['CHANGED_ID']
        
        context = {}
        resp = lambda_handler(event, context, debug=True)
        print(resp)
    

