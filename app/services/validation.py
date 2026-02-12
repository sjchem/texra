
import json
import random
from typing import List, Dict, Any
from agents import Runner
from app.agents.validator import validator_agent
from app.core.logging import get_logger

logger = get_logger("ValidatorService")


async def validate_translation(
    source_text: str,
    translated_text: str,
    target_lang: str,
    source_lang: str = "en"
) -> dict:
    """
    Validate translation quality with comprehensive scoring.

    Args:
        source_text: Original text
        translated_text: Translated text
        target_lang: Target language code
        source_lang: Source language code (default: en)

    Returns:
        Detailed quality assessment dictionary
    """
    prompt = f"""
Source Language: {source_lang}
Target Language: {target_lang}

ORIGINAL TEXT:
{source_text}

TRANSLATED TEXT:
{translated_text}

Evaluate this translation quality and return your assessment in JSON format.
"""

    try:
        result = await Runner.run(
            validator_agent,
            input=prompt.strip()
        )

        # Parse the comprehensive validation result
        validation_result = json.loads(result.final_output)

        # Add metadata
        validation_result["text_length"] = len(source_text)
        validation_result["validation_type"] = "full"

        logger.info(
            f"Validation complete. Quality score: {validation_result.get('quality_score', 'N/A')}, "
            f"Recommendation: {validation_result.get('recommendation', 'N/A')}"
        )

        return validation_result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse validator output: {e}")
        return {
            "quality_score": 0,
            "accuracy_score": 0,
            "completeness_score": 0,
            "fluency_score": 0,
            "terminology_score": 0,
            "issues": [{
                "severity": "critical",
                "type": "validation_error",
                "description": "Validator returned invalid JSON",
                "location": "N/A"
            }],
            "overall_assessment": "Validation failed - unable to assess quality",
            "recommendation": "retranslate",
            "validation_type": "error"
        }
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {
            "quality_score": 0,
            "accuracy_score": 0,
            "completeness_score": 0,
            "fluency_score": 0,
            "terminology_score": 0,
            "issues": [{
                "severity": "critical",
                "type": "system_error",
                "description": str(e),
                "location": "N/A"
            }],
            "overall_assessment": f"Validation error: {str(e)}",
            "recommendation": "review",
            "validation_type": "error"
        }


async def validate_large_document(
    source_chunks: List[str],
    translated_chunks: List[str],
    target_lang: str,
    source_lang: str = "en",
    sample_size: int = 5
) -> dict:
    """
    Validate large documents by sampling random chunks.

    Args:
        source_chunks: List of original text chunks
        translated_chunks: List of translated text chunks
        target_lang: Target language code
        source_lang: Source language code
        sample_size: Number of chunks to sample for validation

    Returns:
        Aggregated quality assessment
    """
    if len(source_chunks) != len(translated_chunks):
        logger.error("Source and translation chunk counts don't match")
        return {
            "quality_score": 0,
            "overall_assessment": "Chunk count mismatch",
            "recommendation": "retranslate"
        }

    # Sample chunks for validation (avoid validating entire large documents)
    num_chunks = len(source_chunks)
    sample_size = min(sample_size, num_chunks)

    if num_chunks <= sample_size:
        sample_indices = list(range(num_chunks))
    else:
        sample_indices = random.sample(range(num_chunks), sample_size)

    logger.info(f"Validating {sample_size} of {num_chunks} chunks")

    # Validate sampled chunks
    validations = []
    for idx in sample_indices:
        result = await validate_translation(
            source_text=source_chunks[idx],
            translated_text=translated_chunks[idx],
            target_lang=target_lang,
            source_lang=source_lang
        )
        validations.append(result)

    # Aggregate scores
    total_quality = sum(v.get("quality_score", 0) for v in validations)
    total_accuracy = sum(v.get("accuracy_score", 0) for v in validations)
    total_completeness = sum(v.get("completeness_score", 0) for v in validations)
    total_fluency = sum(v.get("fluency_score", 0) for v in validations)
    total_terminology = sum(v.get("terminology_score", 0) for v in validations)

    avg_quality = total_quality / len(validations) if validations else 0
    avg_accuracy = total_accuracy / len(validations) if validations else 0
    avg_completeness = total_completeness / len(validations) if validations else 0
    avg_fluency = total_fluency / len(validations) if validations else 0
    avg_terminology = total_terminology / len(validations) if validations else 0

    # Collect all issues
    all_issues = []
    for i, validation in enumerate(validations):
        for issue in validation.get("issues", []):
            issue_copy = issue.copy()
            issue_copy["chunk_index"] = sample_indices[i]
            all_issues.append(issue_copy)

    # Determine overall recommendation
    if avg_quality >= 75:
        recommendation = "pass"
    elif avg_quality >= 60:
        recommendation = "review"
    else:
        recommendation = "retranslate"

    # Assessment summary
    if avg_quality >= 90:
        assessment = f"Excellent translation quality across {sample_size} sampled chunks. Publication-ready."
    elif avg_quality >= 75:
        assessment = f"Good translation quality with minor issues in {len([i for i in all_issues if i['severity'] in ['medium', 'high']])} locations."
    elif avg_quality >= 60:
        assessment = f"Acceptable translation with {len(all_issues)} issues identified. Review recommended."
    else:
        assessment = f"Poor translation quality. Found {len([i for i in all_issues if i['severity'] == 'high'])} major issues."

    return {
        "quality_score": round(avg_quality, 1),
        "accuracy_score": round(avg_accuracy, 1),
        "completeness_score": round(avg_completeness, 1),
        "fluency_score": round(avg_fluency, 1),
        "terminology_score": round(avg_terminology, 1),
        "issues": all_issues,
        "overall_assessment": assessment,
        "recommendation": recommendation,
        "validation_type": "sampled",
        "chunks_validated": sample_size,
        "total_chunks": num_chunks,
        "sample_indices": sample_indices
    }
