#!/usr/bin/env bash
# STARK Translator MCP Server Launcher
# Starts the MCP server for use with Cursor, Claude Desktop, or other MCP clients

set -e

echo "🚀 Starting STARK Translator MCP Server"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "app/mcp_server.py" ]; then
    echo "❌ Error: app/mcp_server.py not found"
    echo "   Please run this script from the stark-translator directory"
    exit 1
fi

# Check for OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY environment variable not set"
    echo "   Checking for .env file..."

    if [ -f ".env" ]; then
        echo "✓ Found .env file, loading..."
        export $(cat .env | grep -v '^#' | xargs)
    else
        echo "❌ Error: No .env file found and OPENAI_API_KEY not set"
        echo ""
        echo "Please either:"
        echo "1. Set OPENAI_API_KEY environment variable:"
        echo "   export OPENAI_API_KEY=your-key-here"
        echo ""
        echo "2. Create a .env file with:"
        echo "   OPENAI_API_KEY=your-key-here"
        exit 1
    fi
fi

echo "✓ Environment configured"
echo ""

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if fastmcp is installed
if ! python -c "import fastmcp" 2>/dev/null; then
    echo "❌ Error: fastmcp not installed"
    echo "   Installing dependencies..."
    pip install -r requirements.txt
fi

echo "✓ Dependencies check passed"
echo ""

# Show available tools
echo "📋 Available MCP Tools:"
echo "   • translate_document - Translate any document format"
echo "   • translate_text - Quick text translation"
echo "   • validate_translation_quality - AI quality assessment"
echo ""

echo "📚 Available MCP Resources:"
echo "   • stark://supported-languages"
echo "   • stark://service-info"
echo ""

echo "🔗 Configuration:"
echo "   • Cursor: ~/.cursor/mcp_settings.json"
echo "   • Claude Desktop: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "   • See MCP_SETUP.md for detailed instructions"
echo ""

echo "========================================"
echo "Starting server... (Press Ctrl+C to stop)"
echo ""

# Start the MCP server
python -m app.mcp_server
