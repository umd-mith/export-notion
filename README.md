# export-notion

Export data stored in Notion for a static website

**This software is early-stage and not intended as a general-purpose Notion API client**

## Usage

You'll need a Notion [Internal Integration Token](https://developers.notion.com/docs/getting-started#create-a-new-integration). The best way to use this is to set it as an environment variable called `NOTION_API_KEY`.

Install in a virtual environment of your choice using the [tarball](https://github.com/umd-mith/export-notion/releases):

```
pip install PATH/TO/TARBALL
```

Basic usage is to provide a Notion database ID. Output will be written to current directory

```
export-notion-pages [OPTIONS] $DATABASE_ID
```

The CLI comes with some help documentation:

```
export-notion-pages --help
```

## Development

```
1. poetry install
2. poetry shell
```
