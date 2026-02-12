# Quality Validation Agent

## Overview

The STARK TRANSLATOR implements a comprehensive **Quality Validation Agent** system that automatically assesses translation quality using AI-powered evaluation. This demonstrates advanced AI orchestration with multi-agent coordination.

## Architecture

### 1. Validator Agent (`app/agents/validator.py`)

A specialized AI agent that evaluates translation quality across multiple dimensions:

**Evaluation Criteria:**
- **Accuracy (40%)**: Meaning preservation, no mistranslations
- **Completeness (30%)**: Nothing omitted or added
- **Fluency (20%)**: Natural language flow
- **Terminology (10%)**: Correct technical term translation

**Output Format:**
```json
{
    "quality_score": 85,
    "accuracy_score": 90,
    "completeness_score": 95,
    "fluency_score": 75,
    "terminology_score": 80,
    "issues": [
        {
            "severity": "high|medium|low",
            "type": "mistranslation|fluency|terminology",
            "description": "Issue description",
            "location": "paragraph 2"
        }
    ],
    "overall_assessment": "Good translation with minor fluency issues",
    "recommendation": "pass|review|retranslate"
}
```

**Quality Scoring:**
- **90-100**: Excellent, publication-ready
- **75-89**: Good, minor improvements possible
- **60-74**: Acceptable, some issues present
- **40-59**: Poor, needs revision
- **0-39**: Unacceptable, must retranslate

### 2. Validation Service (`app/services/validation.py`)

Orchestrates validation workflows:

**Functions:**

#### `validate_translation()`
- Validates single text chunks
- Returns detailed quality assessment
- Handles errors gracefully

#### `validate_large_document()`
- Samples random chunks for efficiency
- Aggregates quality scores
- Identifies issues across document
- Scales validation to large documents

**Features:**
- Random chunk sampling (default: 5 samples)
- Parallel validation processing
- Issue aggregation and reporting
- Error recovery

### 3. Orchestrator Integration (`app/orchestrator.py`)

Seamlessly integrates validation into translation workflows:

**Features:**
- **Optional Validation**: Can be enabled/disabled per request
- **Auto-Retry**: Re-translates chunks scoring <60
- **Progress Tracking**: Stores validation results
- **Summary Generation**: `get_validation_summary()` provides aggregate metrics

**Workflow:**
1. Translate document chunks
2. Sample chunks for validation (5 random)
3. Validate each sample in parallel
4. Auto-retry low-quality translations
5. Store validation results
6. Return quality summary

### 4. API Integration (`app/main.py`)

WebSocket endpoint sends validation results to UI:

```python
# Send validation summary before file
await websocket.send_json({
    "type": "validation",
    "summary": validation_summary
})
```

### 5. UI Display (`streamlit_app.py`)

Beautiful quality dashboard showing:
- **Overall Quality Score** (0-100)
- **Assessment Level** (Excellent/Good/Acceptable/Poor)
- **Issue Breakdown** (Total issues, high-severity count)
- **Recommendation** (pass/review/retranslate)
- **Color-coded Display**:
  - 🟢 Green: 90+ (Excellent)
  - 🟡 Yellow: 75-89 (Good)
  - 🟠 Orange: 60-74 (Acceptable)
  - 🔴 Red: <60 (Poor)

## Usage

### Enable/Disable Validation

By default, validation is **enabled**. To disable:

```python
orchestrator = TranslationOrchestrator()
output_path = await orchestrator.translate(
    file_path,
    target_language,
    enable_validation=False  # Disable validation
)
```

### Get Validation Results

```python
# After translation
summary = orchestrator.get_validation_summary()

# Returns:
{
    "validation_enabled": True,
    "chunks_validated": 5,
    "average_quality_score": 87.2,
    "total_issues": 3,
    "high_severity_issues": 1,
    "recommendation": "pass",
    "assessment": "Good quality"
}
```

## Performance Optimization

### Sampling Strategy

For large documents:
- Validates **5 random chunks** instead of entire document
- Reduces API calls by ~90% for 50-chunk documents
- Maintains statistical reliability

### Parallel Processing

All validations run in parallel:
```python
validation_tasks = [
    asyncio.create_task(validate_chunk(chunk))
    for chunk in sample_chunks
]
results = await asyncio.gather(*validation_tasks)
```

### Auto-Retry Logic

Smart retry for poor translations:
```python
if quality_score < 60:
    new_translation = await translate_text(chunk)
    # Re-validate
    retry_result = await validate_translation(new_translation)
```

## Benefits

1. **Quality Assurance**: Automatic detection of translation issues
2. **User Confidence**: Transparent quality metrics
3. **Error Recovery**: Auto-retry mechanism improves output
4. **Scalability**: Efficient sampling for large documents
5. **Multi-Agent Coordination**: Demonstrates advanced AI orchestration

## Example Output

**UI Display:**
```
┌─────────────────────────────────────────────────┐
│ ✅ Translation Quality: Good quality             │
│                                                  │
│ Quality Score: 87/100                           │
│ Validated: 5 sample segments                    │
│                                                  │
│ Total Issues: 3                                 │
│ High Severity: 1                                │
│ Recommendation: PASS                            │
└─────────────────────────────────────────────────┘
```

## Future Enhancements

- [ ] User-adjustable quality thresholds
- [ ] Detailed issue highlighting in document
- [ ] Terminology consistency checking
- [ ] Style guide enforcement
- [ ] Custom validation rules

## Technical Notes

**Language Model**: `gpt-4o-mini`
**Concurrency**: Parallel validation with semaphore limiting
**Error Handling**: Graceful degradation with default responses
**State Management**: Thread-safe validation result storage

---

This implementation demonstrates **advanced AI engineering** with:
- Multi-agent coordination (Translator ↔ Validator)
- Intelligent agent handoffs
- Quality assurance automation
- Scalable validation strategies
