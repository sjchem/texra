import asyncio
import sys
import os
import tempfile

# Simple test to check validation output
from app.orchestrator import TranslationOrchestrator
from app.core.logging import setup_logging

setup_logging()

async def test():
    # Create a simple test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Hello world. This is a test document for translation validation.")
        f.write("\n\nIt has multiple paragraphs to test the chunking and validation system.")
        f.write("\n\nLet's see if the quality validation agent works correctly.")
        temp_file = f.name
    
    try:
        orchestrator = TranslationOrchestrator()
        
        # Translate with validation enabled
        output = await orchestrator.translate(
            temp_file,
            "Spanish",
            enable_validation=True
        )
        
        # Get validation summary
        summary = orchestrator.get_validation_summary()
        
        print("\n" + "="*60)
        print("VALIDATION SUMMARY:")
        print("="*60)
        import json
        print(json.dumps(summary, indent=2))
        print("="*60)
        
    finally:
        os.unlink(temp_file)
        if os.path.exists(output):
            os.unlink(output)

if __name__ == "__main__":
    asyncio.run(test())
