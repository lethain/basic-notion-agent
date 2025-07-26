
Please implement a typed Python3 project using standard Python practices.
This project is an agent to respond to webhooks from Notion's database changed webhook.

## Functionality





## Server Implementation

It should be implemented as an AWS Lambda, which implement this method, with
the function signature.

    def lambda_handler(event: dict[str, Any], context: dict[str, Any]) -> str:

The `event` parameter has a few important values:

* `event['queryStringParameters']` will be the query parameters in a dictionary:

         "queryStringParameters": {
             "q": "a",
             "z": "b"
         }
* `event['data']` will be the decoded body of the HTTP request, for example:

    { "object": "block", "request_id": "..." }

The response should by a metadata about processing in a JSON encoded string.


## Implementation of `lambda_handler`

Within `lambda_handler`'s implementation, we should perform these steps:

1. Check for a query parameter `client_token` and that it patches the os.env parameter `client_token`.
    If `client_token` is missing from the os.env, don't enforce this check
2. Take `prompt_id` from the query parameters, and retrieve that page from Notion using a `get_page`
    function.
    That function should convert the page into Markdown while preserving the block_ids, for example:

        page_id: oda103f

        block_id: abdecfg
        **This is huge news!**

        block_id: efgc
        [a link](https://destination)

    It's essential to preserve the `block_id`s so that we can comment based on the individual
    blocks rather than only against the whole document.
    We also need the `page_id` so we can comment against the overall page.
3. Then retrieve the blocks from the changed page from Notion as well.
    The page ID will be in the request body in `data.id`.
    Use the same `get_page` function as for the prior step.
4. Return both pages in a JSON encoded dictionary.



## Notion block format and Markdown

Notion's block format is complex and messy. For example, here is the output
of the `results` field of the `/v1/blocks/{id}/children` endpoint:

    [
    {
      "object": "block",
      "id": "c02fc1d3-db8b-45c5-a222-27595b15aea7",
      "parent": {
        "type": "page_id",
        "page_id": "59833787-2cf9-4fdf-8782-e53db20768a5"
      },
      "created_time": "2022-03-01T19:05:00.000Z",
      "last_edited_time": "2022-03-01T19:05:00.000Z",
      "created_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "last_edited_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "has_children": false,
      "archived": false,
      "type": "heading_2",
      "heading_2": {
        "rich_text": [
          {
            "type": "text",
            "text": {
              "content": "Lacinato kale",
              "link": null
            },
            "annotations": {
              "bold": false,
              "italic": false,
              "strikethrough": false,
              "underline": false,
              "code": false,
              "color": "default"
            },
            "plain_text": "Lacinato kale",
            "href": null
          }
        ],
        "color": "default",
        "is_toggleable": false
      }
    },
    {
      "object": "block",
      "id": "acc7eb06-05cd-4603-a384-5e1e4f1f4e72",
      "parent": {
        "type": "page_id",
        "page_id": "59833787-2cf9-4fdf-8782-e53db20768a5"
      },
      "created_time": "2022-03-01T19:05:00.000Z",
      "last_edited_time": "2022-03-01T19:05:00.000Z",
      "created_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "last_edited_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "has_children": false,
      "archived": false,
      "type": "paragraph",
      "paragraph": {
        "rich_text": [
          {
            "type": "text",
            "text": {
              "content": "Lacinato kale is a variety of kale with a long tradition in Italian cuisine, especially that of Tuscany. It is also known as Tuscan kale, Italian kale, dinosaur kale, kale, flat back kale, palm tree kale, or black Tuscan palm.",
              "link": {
                "url": "https://en.wikipedia.org/wiki/Lacinato_kale"
              }
            },
            "annotations": {
              "bold": false,
              "italic": false,
              "strikethrough": false,
              "underline": false,
              "code": false,
              "color": "default"
            },
            "plain_text": "Lacinato kale is a variety of kale with a long tradition in Italian cuisine, especially that of Tuscany. It is also known as Tuscan kale, Italian kale, dinosaur kale, kale, flat back kale, palm tree kale, or black Tuscan palm.",
            "href": "https://en.wikipedia.org/wiki/Lacinato_kale"
          }
        ],
        "color": "default"
      }
    }
    ]

We want to interact with that as Markdown text.
Similarly, we want to transform Markdown responses into
that format before we return it to Notion.


Please implement two functions to handle converting between Notion's
blocks format and Markdown:

* `notion_to_markdown` should take Notion blocks and turn it into Markdown
* `markdown_to_notion` should do the opposite, turning Markdown into Notion blocks


## Notion webhooks and APIs

This lambda will be triggered by HTTP messages, e.g. webhooks,
coming from Notion wherever a page has been modified.
A full example of that document is in `../messages/automation_webhook.json`,
but here is a short example including only the fields we care about:

    {
      "source": {
        "type": "automation"
      },
      "data": {
        "object": "page",
        "id": "23cac777-210d-80a8-a27d-e505f0cdf316"
      }
      "url": "https:www.notion.soTest-test-test-23cac777210d80a8a27de505f0cdf316",
      "request_id": "0115d9dd-203e-4003-b304-dead337b9eee"      
    }

From within that object, what you really care about is `data.id` which will be
used by the `https://api.notion.com/v1/blocks/{data.id}/children` API to retrieve
all the children of that page.

### Retrieving blocks via Notion API

The `https://api.notion.com/v1/blocks/{data.id}/children` API 
is documented in the [Retrieve block children](https://developers.notion.com/reference/get-block-children) page,
and should be used to retrieve any page. In this script, there are three scenarios where we might use this:

1. Retrieving the page for the prompt
2. Retrieving the page for the document
3. Recursively retrieving documents mentioned in the prompt document
    to build the context window out to a maximum size

The format of the responses from that endpoint are:

{
  "object": "list",
  "results": [
    {
      "object": "block",
      "id": "c02fc1d3-db8b-45c5-a222-27595b15aea7",
      "parent": {
        "type": "page_id",
        "page_id": "59833787-2cf9-4fdf-8782-e53db20768a5"
      },
      "created_time": "2022-03-01T19:05:00.000Z",
      "last_edited_time": "2022-03-01T19:05:00.000Z",
      "created_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "last_edited_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "has_children": false,
      "archived": false,
      "type": "heading_2",
      "heading_2": {
        "rich_text": [
          {
            "type": "text",
            "text": {
              "content": "Lacinato kale",
              "link": null
            },
            "annotations": {
              "bold": false,
              "italic": false,
              "strikethrough": false,
              "underline": false,
              "code": false,
              "color": "default"
            },
            "plain_text": "Lacinato kale",
            "href": null
          }
        ],
        "color": "default",
        "is_toggleable": false
      }
    },
    {
      "object": "block",
      "id": "acc7eb06-05cd-4603-a384-5e1e4f1f4e72",
      "parent": {
        "type": "page_id",
        "page_id": "59833787-2cf9-4fdf-8782-e53db20768a5"
      },
      "created_time": "2022-03-01T19:05:00.000Z",
      "last_edited_time": "2022-03-01T19:05:00.000Z",
      "created_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "last_edited_by": {
        "object": "user",
        "id": "ee5f0f84-409a-440f-983a-a5315961c6e4"
      },
      "has_children": false,
      "archived": false,
      "type": "paragraph",
      "paragraph": {
        "rich_text": [
          {
            "type": "text",
            "text": {
              "content": "Lacinato kale is a variety of kale with a long tradition in Italian cuisine, especially that of Tuscany. It is also known as Tuscan kale, Italian kale, dinosaur kale, kale, flat back kale, palm tree kale, or black Tuscan palm.",
              "link": {
                "url": "https://en.wikipedia.org/wiki/Lacinato_kale"
              }
            },
            "annotations": {
              "bold": false,
              "italic": false,
              "strikethrough": false,
              "underline": false,
              "code": false,
              "color": "default"
            },
            "plain_text": "Lacinato kale is a variety of kale with a long tradition in Italian cuisine, especially that of Tuscany. It is also known as Tuscan kale, Italian kale, dinosaur kale, kale, flat back kale, palm tree kale, or black Tuscan palm.",
            "href": "https://en.wikipedia.org/wiki/Lacinato_kale"
          }
        ],
        "color": "default"
      }
    }
  ],
  "next_cursor": null,
  "has_more": false,
  "type": "block",
  "block": {}
}

Use the `notion_to_markdown` function describe above to convert the blocks into
an easy to understand format. If `next_cursor` if specified, then perform another
API call with the value of `next_cursor` used as the `start_cursor` query parameter
as described in [Pagination](https://developers.notion.com/reference/intro#pagination) documentation.






