# basic-notion-agent
A very simple agent to use Notion documents as prompts to comment on other Notion documents.


## Deployment

Create an AWS Lambda and then upload `packaged/agent.zip` or
build your own version using:

    make lambda-package

Then upload `agent.zip` to your AWS Lambda.

Afterwards, ensure these environmental parameters are set in AWS:

* `CLIENT_TOKEN` should be a token you include in your calls to this lambda via
    the `client_id` query parameter
* `NOTION_TOKEN` should be your Notion API api token
* `OPENAI_API_KEY` should be your OpenAI API key


## Testing Locally

For validation, debugging and development purposes, you should
strongly prefer local development.

Setup a Notion instance with a page to use as a prompt,
and a page that you want to apply the prompt against.

Create a copy of
`test.json.scaffold', name it `test.json`
and fill in the values with your correct values.
This will look like:

    {
        "NOTION_TOKEN": "your-notion-token",
        "OPENAI_API_KEY": "your-openai-api-key",
        "PROMPT_ID": "page-id-for-your-prompt-page-in-notion",
        "CHANGED_ID": "page-id-for-your-page-to-comment-on-in-notion"
    }

Ensure you have installed openai's client:

    pip install -r requirements.txt


Then run:

    python3 lambda_function.py

This will create two local files:

    * `prompt.txt` is the full representation of the prompt page sent to OpenAI
    * `changed.txt` is the full representation of the page to comment on sent to OpenAI

These are exceptionally useful for debugging.

