import os
import shutil
from pathlib import Path
from typing import Dict, Any
from docx import Document
from app.config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

def fill_protocol(template_path: str, output_path: str, data: Dict[str, Any]) -> bool:
    """
    Fill a Word template with provided data and save to output path.
    
    Args:
        template_path: Path to the Word template file
        output_path: Path where to save the filled document
        data: Dictionary with key-value pairs to replace in the template
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Starting to fill protocol template: {template_path}")
    logger.debug(f"Output path: {output_path}")
    logger.debug(f"Data keys: {list(data.keys())}")
    
    try:
        # Validate template exists
        if not os.path.exists(template_path):
            logger.error(f"Template file not found: {template_path}")
            return False
            
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            logger.debug(f"Created output directory: {output_dir}")
            
        # Create a copy of the template
        logger.debug("Creating template copy")
        shutil.copy(template_path, output_path)
        
        # Load the document
        doc = Document(output_path)
        
        def replace_text_in_paragraphs(paragraphs):
            """Helper to replace text in document paragraphs"""
            replacements = 0
            for p in paragraphs:
                # First, check if any markers exist in the full paragraph text
                full_text = ''.join(run.text for run in p.runs)
                
                for key, value in data.items():
                    marker = f"{{{{{key}}}}}"
                    if marker not in full_text:
                        continue
                        
                    # If we get here, the marker exists in this paragraph
                    logger.debug(f"Replacing marker: {marker} with value")
                    
                    # Process each run to find and replace the marker while preserving formatting
                    for run in p.runs:
                        if marker in run.text:
                            # Store original formatting
                            original_text = run.text
                            
                            # Replace only the marker, keep the rest of the text
                            run.text = original_text.replace(marker, str(value))
                            
                            replacements += 1
                            logger.debug(f"Replaced {marker} in paragraph")
                            break
            
            return replacements

        # Process document content
        logger.debug("Processing document content")
        total_replacements = 0
        
        # Replace in paragraphs
        para_replacements = replace_text_in_paragraphs(doc.paragraphs)
        total_replacements += para_replacements
        logger.debug(f"Made {para_replacements} replacements in paragraphs")
        
        # Replace in tables
        table_replacements = 0
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    # Process each paragraph in the cell
                    for paragraph in cell.paragraphs:
                        full_text = ''.join(run.text for run in paragraph.runs)
                        
                        for key, value in data.items():
                            marker = f"{{{{{key}}}}}"
                            if marker not in full_text:
                                continue
                                
                            # Process each run to find and replace the marker
                            for run in paragraph.runs:
                                if marker in run.text:
                                    # Store original formatting
                                    original_text = run.text
                                    
                                    # Replace only the marker, keep the rest of the text
                                    run.text = original_text.replace(marker, str(value))
                                    
                                    table_replacements += 1
                                    logger.debug(f"Replaced {marker} in table cell")
                                    break
        
        total_replacements += table_replacements
        logger.debug(f"Made {table_replacements} replacements in tables")
        
        if total_replacements == 0:
            logger.warning("No template markers were replaced in the document")
        else:
            logger.info(f"Successfully made {total_replacements} replacements in the document")
        
        # Save the document
        doc.save(output_path)
        logger.info(f"Successfully saved filled document to: {output_path}")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission error when accessing files: {e}")
        return False
    except Exception as e:
        logger.error(f"Error filling protocol template: {e}", exc_info=True)
        # Clean up partially created file if it exists
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                logger.debug(f"Removed partially created file: {output_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up partially created file: {cleanup_error}")
        return False