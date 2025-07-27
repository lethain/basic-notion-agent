# basic-notion-agent
A very simple agent to use Notion documents as prompts to comment on other Notion documents.


## Deployment

Create an AWS Lambda and then copy `main.py` as the implementation, e.g.

    cat main.py | pbcopy
    <paste into aws console>

Then ensure these environmental parameters are set in AWS:

* `CLIENT_TOKEN` should be a token you include in your calls to this lambda via
    the `client_id` query parameter
* `NOTION_TOKEN` should be your Notion API api token
* `OPENAI_API_KEY` should be your OpenAI API key




## Testing

To test this functionality, create a copy of
`test.json.scaffold', name it `test.json`
and fill in the values with your correct values.
This will look like:

    {
        "NOTION_TOKEN": "your-notion-token",
        "OPENAI_API_KEY": "your-openai-api-key",
        "PROMPT_ID": "page-id-for-your-prompt-page-in-notion",
        "CHANGED_ID": "page-id-for-your-page-to-comment-on-in-notion"
    }

Then run:

    python3 main.py

It uses only standard library values.
Note that you need a real working Notion instance to call the APIs against.

This will create two local files:

    * `prompt.txt` is the full representation of the prompt page sent to OpenAI
    * `changed.txt` is the full representation of the page to comment on sent to OpenAI

These are exceptionally useful for debugging.

