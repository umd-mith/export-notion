import typer
import httpx
from httpx import HTTPStatusError
import time
from pathlib import Path


def create_client(
    api_key: str,
    http_timeout: int,
    user_agent: str,
):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2021-05-13",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
    }

    timeout = httpx.Timeout(5, read=http_timeout)
    client = httpx.Client(headers=headers, timeout=timeout)

    return client


def get_db_pages(client: httpx.Client, db: str, sleep=0.3):
    first = True
    offset = None
    while first or offset:
        first = False
        url = f"https://api.notion.com/v1/databases/{db}/query"
        response = client.post(url, data={})
        response.raise_for_status()
        data = response.json()
        offset = data.get("next_cursor")
        yield from data["results"]
        if offset and sleep:
            time.sleep(sleep)


def get_page_contents(client: httpx.Client, page: str, page_size=100, sleep=0.3):
    first = True
    offset = None
    while first or offset:
        first = False
        url = f"https://api.notion.com/v1/blocks/{page}/children"
        response = client.get(url, params={"page_size": page_size})
        response.raise_for_status()
        data = response.json()
        offset = data.get("next_cursor")
        yield from data["results"]
        if offset and sleep:
            time.sleep(sleep)


def check_annotations(textobject: dict[str, str]):
    annotations = {
        k: v
        for k, v in textobject["annotations"].items()
        if v not in [False, "default"]
    }

    if annotations != {}:
        return annotations
    else:
        return None


def handle_heading_3(content):
    if len(content) > 1:
        raise RuntimeError(f"Heading error. Expect length 1, got length {len(content)}")

    text = content[0]
    if text["type"] != "text":
        raise RuntimeError("Unhandled type")

    if not text["text"]["link"]:
        return f"### {text['text']['content']}\n"
    else:
        return f"### [{text['text']['content']}]({text['text']['link']['url']})\n"


def handle_bulleted_list_item(content):
    if len(content) > 1:
        raise RuntimeError(
            f"List item error. Expect length 1, got length {len(content)}"
        )

    text = content[0]
    if text["type"] != "text":
        raise RuntimeError("Unhandled type")

    if not text["text"]["link"]:
        return f"* {text['text']['content']}\n"
    else:
        return f"* [{text['text']['content']}]({text['text']['link']['url']})\n"


def handle_subtext(text):
    if not text["text"]["link"]:
        return f"{text['text']['content']}"
    else:
        return f"[{text['text']['content']}]({text['text']['link']['url']})"


def handle_paragraph(content):
    para_contents = []
    for subtext in content:
        para_contents.append(handle_subtext(subtext))

    return f"{''.join(para_contents)}\n"


def process_block(blk: dict[str, object]):
    blk_type = blk.get("type")
    blk_body = blk[blk_type]["text"]

    if blk_type == "heading_3":
        blk_content = handle_heading_3(blk_body)
    if blk_type == "paragraph":
        blk_content = handle_paragraph(blk_body)
    if blk_type == "bulleted_list_item":
        blk_content = handle_bulleted_list_item(blk_body)

    return blk_content


def output_callback(value: Path):
    if not value.exists():
        raise typer.BadParameter(f"Output path '{value}' does not exist")
    if not value.is_dir():
        raise typer.BadParameter("Output path must be a directory")
    return value


def writer(pageobj: dict[str, str], output_path: Path):
    outfile = f"{'-'.join(pageobj['title'].lower().split())}.md"
    with open(Path(output_path / outfile), "w") as mdfile:
        mdfile.write("---")
        mdfile.write(f"\ntitle: {pageobj['title']}")
        mdfile.write(f"\nnotion_id: {pageobj['page_id']}")
        mdfile.write(f"\nlast_modified_time: {pageobj['last_modified_time']}")
        mdfile.write("\n---")
        mdfile.write(f"\n{pageobj['content']}")


def main(
    database: str = typer.Argument(
        ...,
        help="The identifier of the database you want to use. It should be a 36 character string (may contain hyphens or not)",
    ),
    output_path: Path = typer.Argument(
        ".",
        callback=output_callback,
        help="Where to save your content",
    ),
    user_agent: str = typer.Argument(
        "curl/7.64.1", help="User-agent string for requests"
    ),
    http_timeout: int = typer.Argument(5, help="Timeout (in seconds) for API requests"),
    key: str = typer.Argument(..., envvar="NOTION_API_KEY"),
):
    """Export Notion content to a directory of local markdown files."""
    client = create_client(key, http_timeout, user_agent)
    typer.secho(f"Downloading from database {database}")
    typer.secho(
        f"Writing output to {Path(output_path).resolve().as_posix()}",
        fg=typer.colors.CYAN,
    )

    out_dir = Path(output_path).resolve()
    for page in get_db_pages(client, database):
        pagedata = {}
        try:
            if isinstance(page, list):
                # TODO: Handle multiple top-level pages
                pass
            if isinstance(page, dict):
                if page["object"] != "page":
                    raise RuntimeError("Query didn't return a page")

            name = page["properties"]["Name"]
            if name["type"] == "title":
                pagedata["title"] = name["title"][0]["plain_text"]
            pagedata["page_id"] = page["id"]
            pagedata["last_modified_time"] = page["last_edited_time"]

            page_content = get_page_contents(client, page["id"])
            pagebody = []
            for block in page_content:
                if block["has_children"] is not False:
                    child_content = get_page_contents(client, block["id"])
                    for c in child_content:
                        pagebody.append(process_block(c))
                else:
                    pagebody.append(process_block(block))

            pagedata["content"] = "".join(pagebody)

            writer(pagedata, output_path)

        except HTTPStatusError as err:
            err_report_base = typer.style(
                "API request returned an error", fg=typer.colors.BRIGHT_RED
            )
            typer.echo(err_report_base + err)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
