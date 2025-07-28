# basic-notion-agent
A very simple agent to use Notion documents as prompts to comment on other Notion documents.


## Configuring Notion

The steps to configuring in Notion are:

1. Create a [Notion integration](https://www.notion.so/profile/integrations).
    Ensure it has ability to read content, read comments, and insert comments.
    It should also have the ability to retrieve user information.

    Also update the `Access` tab for your integration to include the workspaces
    where your Notion pages exist.
2. Then add an automation to a database in one of the enabled workspaces which
    sends requests to:

        https://yourawslambda/
        ?prompt_id=notion-page-for-your-prompt
        &client_token=a-unique-key
        &page_comment=false
        &model=gpt-4.1

    Note that the URL for your lambda won't exist until you finish setting up the agent as described
    in "Deploying on AWS" below.
    
    Only `prompt_id` is required. Explaining them a bit:

    * `prompt_id` is the Notion page id for the prompt that should be used to evaluate the changed page
    * `client_token` must match the `CLIENT_TOKEN` in the lambda's environment,
        if not, the request will be rejected.
        This is a client secret
    * `page_comment` defaults to true, and determines whether the final reply from the
        OpenAI model is added as a comment on the page itself. If the value is set to false,
        then only inline comments will be made
    * `model` is the OpenAI model string if you want to use different models for different scenarios
3. You could alternatively avoid the database approach and instead have your agent
    get webhooks for every change by configuring `Webhook`.
    It really just depends on the setup you're looking to provide.
4. Notion should be configuredf at this point.


## Deploying on AWS

Create an AWS Lambda and then upload `packaged/agent.zip` or
build your own version using:

    make lambda-package

Then upload `agent.zip` to your AWS Lambda.

Afterwards, ensure these environmental parameters are set in AWS:

* `CLIENT_TOKEN` should be a token you include in your calls to this lambda via
    the `client_id` query parameter
* `NOTION_TOKEN` should be your Notion API api token
* `OPENAI_API_KEY` should be your OpenAI API key

Also increase the timeout to at least three minutes.
(It usually won't take that long, but it really just depends
on size of prompt and changed pages.)


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

