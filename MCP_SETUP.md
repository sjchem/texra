# STARK Translator - MCP Server Setup

## What is MCP?

**Model Context Protocol (MCP)** is a standard protocol that allows AI assistants to connect to external tools and data sources. This enables you to use STARK Translator directly from AI coding assistants like **Cursor** or **Claude Desktop**.

## Features

The STARK Translator MCP server provides:

### 🔧 Tools (3)
1. **`translate_document`** - Translate any document (PDF, DOCX, PPTX, images)
2. **`translate_text`** - Quick text-only translation
3. **`validate_translation_quality`** - AI-powered quality assessment

### 📚 Resources (2)
1. **`stark://supported-languages`** - List of supported languages
2. **`stark://service-info`** - Service capabilities and limits

## Quick Start

### 1. Install Dependencies

```bash
pip install mcp fastmcp
```

### 2. Run the MCP Server

```bash
cd /path/to/stark-translator
python -m app.mcp_server
```

The server will start and listen for MCP connections.

## Configuration for AI Assistants

### Cursor Configuration

Add to your Cursor MCP settings (`~/.cursor/mcp_settings.json`):

```json
{
  "mcpServers": {
    "stark-translator": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/stark-translator",
      "env": {
        "OPENAI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Claude Desktop Configuration

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "stark-translator": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/stark-translator",
      "env": {
        "OPENAI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

### Using with Docker

If you prefer to run via Docker:

```json
{
  "mcpServers": {
    "stark-translator": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env", "OPENAI_API_KEY=your-key",
        "stark-translator-mcp"
      ]
    }
  }
}
```

## Usage Examples

### Example 1: Translate a PDF from Cursor

In Cursor, ask:
```
"Use the stark-translator tool to translate my contract.pdf to Spanish"
```

The AI will:
1. Read your PDF file
2. Call `translate_document` tool
3. Save the translated PDF
4. Show you quality validation results

### Example 2: Quick Text Translation

```
"Translate 'Hello, how are you?' to French using stark-translator"
```

### Example 3: Validate Translation Quality

```
"Check the quality of this translation using stark-translator:
Source: 'The quick brown fox'
Translation: 'El rápido zorro marrón'"
```

## Available Tools Reference

### 1. translate_document

```python
result = await translate_document(
    file_bytes=pdf_content,
    target_language="Spanish",
    filename="report.pdf",
    enable_validation=True,
    output_format="PDF"  # or "DOCX", "PPTX"
)
```

**Returns:**
```json
{
  "translated_bytes": "<bytes>",
  "validation_summary": {
    "average_quality_score": 87.5,
    "recommendation": "pass",
    "chunks_validated": 5
  },
  "output_filename": "translated_report.pdf",
  "file_size_kb": 245.3
}
```

### 2. translate_text

```python
result = await translate_text(
    text="Hello world",
    target_language="German"
)
```

**Returns:**
```json
{
  "translated_text": "Hallo Welt",
  "character_count": 11,
  "success": true
}
```

### 3. validate_translation_quality

```python
result = await validate_translation_quality(
    source_text="Hello",
    translated_text="Hola",
    target_language="Spanish"
)
```

**Returns:**
```json
{
  "quality_score": 95,
  "accuracy_score": 100,
  "completeness_score": 100,
  "fluency_score": 90,
  "terminology_score": 85,
  "issues": [],
  "recommendation": "pass"
}
```

## Resources Reference

### stark://supported-languages

Returns list of supported languages and file formats:

```json
{
  "major_languages": [
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    ...
  ],
  "supported_formats": [
    "PDF (.pdf)",
    "Word (.docx)",
    "PowerPoint (.pptx)",
    ...
  ]
}
```

### stark://service-info

Returns service capabilities:

```json
{
  "service": "STARK Translator",
  "capabilities": {
    "max_file_size": "200MB",
    "quality_validation": true,
    "format_preservation": true
  }
}
```

## Troubleshooting

### Server won't start

**Check Python environment:**
```bash
python --version  # Should be 3.10+
pip list | grep mcp  # Should show fastmcp
```

**Check working directory:**
```bash
cd /path/to/stark-translator
python -m app.mcp_server
# Should show: "🚀 Starting STARK Translator MCP Server"
```

### API Key Issues

Make sure `OPENAI_API_KEY` is set:
```bash
echo $OPENAI_API_KEY
```

Or add to `.env` file in project root:
```
OPENAI_API_KEY=sk-...
```

### Connection Issues in Cursor/Claude

1. Restart the AI assistant
2. Check logs in the assistant's developer console
3. Verify the MCP server is running: `ps aux | grep mcp_server`

## Advanced Usage

### Batch Translation

Use the MCP server in a script:

```python
import asyncio
from mcp.client import ClientSession, StdioServerParameters

async def batch_translate():
    async with ClientSession(
        StdioServerParameters(
            command="python",
            args=["-m", "app.mcp_server"],
            cwd="/path/to/stark-translator"
        )
    ) as session:
        for file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
            with open(file, "rb") as f:
                result = await session.call_tool(
                    "translate_document",
                    {
                        "file_bytes": f.read(),
                        "target_language": "Spanish",
                        "filename": file
                    }
                )
                # Save result...
```

### Custom Integration

Build your own MCP client:

```python
from mcp.client import ClientSession, StdioServerParameters

server_params = StdioServerParameters(
    command="python",
    args=["-m", "app.mcp_server"],
    cwd="/path/to/stark-translator"
)

async with ClientSession(server_params) as session:
    # List available tools
    tools = await session.list_tools()

    # Call a tool
    result = await session.call_tool(
        "translate_text",
        {"text": "Hello", "target_language": "French"}
    )
```

## Performance Notes

- **Small documents (<20 pages):** 5-15 seconds
- **Large documents (20-100 pages):** 30-120 seconds
- **Very large (100-200 pages):** 2-5 minutes

MCP connections are stateful - the server stays running for fast subsequent calls.

## Security

- Never commit API keys
- Use environment variables for secrets
- MCP server runs locally - files never leave your machine (except API calls)
- Validate file types before processing

## Next Steps

1. ✅ Install and test basic translation
2. 📝 Try different file formats (PDF, DOCX, PPTX)
3. 🔍 Test quality validation
4. 🚀 Integrate into your workflow (Cursor/Claude Desktop)
5. 🎯 Build custom automations

## Support

For issues or questions:
- Check logs: `python -m app.mcp_server --verbose`
- Review STARK Translator documentation
- Test tools individually before batch processing

---

**STARK Translator MCP Server** - Making AI-powered translation accessible from any AI assistant.
