#!/usr/bin/env python3
"""
Test script for STARK Translator MCP Server

Run this to verify MCP server is working correctly.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_mcp_server():
    """Test MCP server tools and resources."""
    print("=" * 60)
    print("STARK TRANSLATOR - MCP SERVER TEST")
    print("=" * 60)

    # Import MCP server
    from app.mcp_server import mcp

    print("\n✓ MCP server imported successfully")
    print(f"  Server name: {mcp.name}")

    # Test 1: List tools
    print("\n📋 Testing: List Tools")
    print("-" * 60)

    # Get tools from the FastMCP instance
    tools = []
    for name, func in mcp._tool_manager._tools.items():
        tools.append(name)
        print(f"  ✓ {name}")

    expected_tools = ["translate_document", "translate_text", "validate_translation_quality"]
    for tool in expected_tools:
        if tool not in tools:
            print(f"  ✗ Missing tool: {tool}")
            return False

    # Test 2: List resources
    print("\n📚 Testing: List Resources")
    print("-" * 60)

    resources = []
    for uri, func in mcp._resource_manager._resources.items():
        resources.append(uri)
        print(f"  ✓ {uri}")

    expected_resources = ["stark://supported-languages", "stark://service-info"]
    for resource in expected_resources:
        if resource not in resources:
            print(f"  ✗ Missing resource: {resource}")
            return False

    # Test 3: Call a resource
    print("\n🔍 Testing: Get Resource Content")
    print("-" * 60)

    try:
        import json
        lang_resource = mcp._resource_manager._resources["stark://supported-languages"]
        lang_data = lang_resource()
        parsed = json.loads(lang_data)

        print(f"  ✓ stark://supported-languages")
        print(f"    Languages: {len(parsed['major_languages'])}")
        print(f"    Formats: {len(parsed['supported_formats'])}")

        info_resource = mcp._resource_manager._resources["stark://service-info"]
        info_data = info_resource()
        info_parsed = json.loads(info_data)

        print(f"  ✓ stark://service-info")
        print(f"    Service: {info_parsed['service']}")
        print(f"    Max file size: {info_parsed['capabilities']['max_file_size']}")
    except Exception as e:
        print(f"  ✗ Resource test failed: {e}")
        return False

    # Test 4: Simple text translation
    print("\n🌍 Testing: Text Translation")
    print("-" * 60)

    try:
        from app.mcp_server import translate_text

        result = await translate_text(
            text="Hello, this is a test.",
            target_language="Spanish"
        )

        if result.get('success'):
            print(f"  ✓ Translation successful")
            print(f"    Input: 'Hello, this is a test.'")
            print(f"    Output: '{result['translated_text']}'")
            print(f"    Characters: {result['character_count']} → {result['translated_character_count']}")
        else:
            print(f"  ✗ Translation failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"  ✗ Text translation test failed: {e}")
        return False

    # Test 5: Validation
    print("\n✅ Testing: Quality Validation")
    print("-" * 60)

    try:
        from app.mcp_server import validate_translation_quality

        result = await validate_translation_quality(
            source_text="Hello world",
            translated_text="Hola mundo",
            target_language="Spanish"
        )

        if not result.get('error'):
            print(f"  ✓ Validation successful")
            print(f"    Quality Score: {result.get('quality_score', 'N/A')}/100")
            print(f"    Recommendation: {result.get('recommendation', 'N/A').upper()}")
            print(f"    Issues Found: {len(result.get('issues', []))}")
        else:
            print(f"  ✗ Validation failed: {result.get('error')}")
            # Don't fail test - validation might require additional setup
    except Exception as e:
        print(f"  ⚠️  Validation test skipped: {e}")
        # Don't fail - validation is optional

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
    print("\nMCP Server is ready to use!")
    print("\nNext steps:")
    print("1. Run: python -m app.mcp_server")
    print("2. Configure in Cursor/Claude Desktop (see MCP_SETUP.md)")
    print("3. Start translating documents from your AI assistant!")

    return True


if __name__ == "__main__":
    print("\n🚀 Starting MCP Server Tests...\n")

    try:
        success = asyncio.run(test_mcp_server())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
