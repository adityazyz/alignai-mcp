# ./agents/content_generation.py
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from tools.sse_tools import send_sse
import logging
from typing import Dict, Any, Optional, List
import os
from models import GeneratedContent
import json
import re

load_dotenv()
llm = ChatNVIDIA(model=os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct"), temperature=0)
logger = logging.getLogger(__name__)

def smart_match_participant_id(name: str, participants: list) -> str:
    """
    Intelligently match a name from transcription to a participant ID.
    Returns the best matching participant ID or default fallback.
    """
    if not name or not participants:
        logger.warning(f"No name or participants provided for matching. Name: '{name}', Participants: {participants}")
        return get_default_participant_id(participants)
    
    name_lower = name.lower().strip()
    
    # Try exact matches first
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        # Try full name match
        if 'firstName' in participant and 'lastName' in participant:
            full_name = f"{participant['firstName']} {participant['lastName']}".lower().strip()
            if name_lower == full_name:
                participant_id = participant.get("id", participant.get("email", ""))
                logger.debug(f"Exact full name match: '{name}' -> ID: '{participant_id}'")
                return participant_id
            
        # Try single name field match
        if 'name' in participant:
            participant_name = participant['name'].lower().strip()
            if name_lower == participant_name:
                participant_id = participant.get("id", participant.get("email", ""))
                logger.debug(f"Exact single name match: '{name}' -> ID: '{participant_id}'")
                return participant_id
    
    # Try partial matches
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        if 'firstName' in participant and 'lastName' in participant:
            first_name = participant['firstName'].lower().strip()
            last_name = participant['lastName'].lower().strip()
            if name_lower == first_name or name_lower == last_name:
                participant_id = participant.get("id", participant.get("email", ""))
                logger.debug(f"Partial name match: '{name}' -> ID: '{participant_id}'")
                return participant_id
        
        if 'name' in participant:
            participant_name = participant['name'].lower().strip()
            if name_lower in participant_name or participant_name in name_lower:
                participant_id = participant.get("id", participant.get("email", ""))
                logger.debug(f"Partial name containment match: '{name}' -> ID: '{participant_id}'")
                return participant_id
    
    logger.warning(f"No match found for name '{name}'. Using default ID.")
    return get_default_participant_id(participants)

def smart_match_participant_emails(names: List[str], participants: list, exclude_creator_id: str = None) -> str:
    """
    Match multiple recipient names to their email addresses and return as comma-separated string.
    Excludes the creator's email to prevent self-sending.
    """
    if not names or not participants:
        logger.warning(f"No names or participants provided for email matching. Names: {names}, Participants: {participants}")
        return get_default_participant_email(participants, exclude_creator_id)
    
    matched_emails = []
    creator_email = None
    
    # Find creator's email to exclude it
    if exclude_creator_id:
        for participant in participants:
            if isinstance(participant, dict) and participant.get("id") == exclude_creator_id:
                creator_email = participant.get("email", participant.get("id", ""))
                break
    
    for name in names:
        if not name or name.lower().strip() == "default":
            continue
            
        name_lower = name.lower().strip()
        matched = False
        
        # Try exact matches first
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            # Try full name match
            if 'firstName' in participant and 'lastName' in participant:
                full_name = f"{participant['firstName']} {participant['lastName']}".lower().strip()
                if name_lower == full_name:
                    email = participant.get("email", participant.get("id", ""))
                    # Exclude creator's email and avoid duplicates
                    if email and email not in matched_emails and email != "ai" and email != creator_email:
                        matched_emails.append(email)
                        matched = True
                        logger.debug(f"Exact full name match for recipient: '{name}' -> Email: '{email}'")
                        break
                
            # Try single name field match
            if 'name' in participant:
                participant_name = participant['name'].lower().strip()
                if name_lower == participant_name:
                    email = participant.get("email", participant.get("id", ""))
                    # Exclude creator's email and avoid duplicates
                    if email and email not in matched_emails and email != "ai" and email != creator_email:
                        matched_emails.append(email)
                        matched = True
                        logger.debug(f"Exact single name match for recipient: '{name}' -> Email: '{email}'")
                        break
        
        # Try partial matches if no exact match
        if not matched:
            partial_matches = []
            for participant in participants:
                if not isinstance(participant, dict):
                    continue
                if 'firstName' in participant and 'lastName' in participant:
                    first_name = participant['firstName'].lower().strip()
                    last_name = participant['lastName'].lower().strip()
                    if name_lower == first_name or name_lower == last_name:
                        email = participant.get("email", participant.get("id", ""))
                        if email and email != "ai" and email != creator_email:
                            partial_matches.append(email)
                
                if 'name' in participant:
                    participant_name = participant['name'].lower().strip()
                    if name_lower in participant_name or participant_name in name_lower:
                        email = participant.get("email", participant.get("id", ""))
                        if email and email != "ai" and email != creator_email:
                            partial_matches.append(email)
            
            if len(partial_matches) == 1:
                if partial_matches[0] not in matched_emails:
                    matched_emails.append(partial_matches[0])
                    logger.debug(f"Single partial match for recipient: '{name}' -> Email: '{partial_matches[0]}'")
            elif len(partial_matches) > 1:
                logger.warning(f"Multiple partial matches for recipient '{name}': {partial_matches}. Using first match.")
                if partial_matches[0] not in matched_emails:
                    matched_emails.append(partial_matches[0])
    
    # Return comma-separated string of matched emails, or default if none found
    if matched_emails:
        return ", ".join(matched_emails)
    
    logger.warning("No valid recipient emails found. Using default email.")
    return get_default_participant_email(participants, exclude_creator_id)

def get_default_participant_id(participants: list) -> str:
    """Get a default valid participant ID for fallback cases."""
    if not participants:
        logger.warning("No participants available for default ID. Returning 'ai'.")
        return "ai"
    
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        participant_id = participant.get("id")
        if participant_id and participant_id != "ai":
            logger.debug(f"Using default participant ID: '{participant_id}'")
            return participant_id
        email = participant.get("email")
        if email and email != "ai":
            logger.debug(f"Using default participant email as ID: '{email}'")
            return email
    
    logger.warning("No valid default participant ID found. Returning 'ai'.")
    return "ai"

def get_default_participant_email(participants: list, exclude_creator_id: str = None) -> str:
    """Get a default valid participant email for fallback cases, excluding creator."""
    if not participants:
        logger.warning("No participants available for default email. Returning 'ai'.")
        return "ai"
    
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        # Skip if this is the creator
        if exclude_creator_id and participant.get("id") == exclude_creator_id:
            continue
            
        email = participant.get("email")
        if email and email != "ai":
            logger.debug(f"Using default participant email: '{email}'")
            return email
        participant_id = participant.get("id")
        if participant_id and participant_id != "ai":
            logger.debug(f"Using default participant ID as email: '{participant_id}'")
            return participant_id
    
    logger.warning("No valid default participant email found. Returning 'ai'.")
    return "ai"

async def generate_content(transcription: str, content_details: dict, attendees: list, participants: list, organization_id: str, department_id: str) -> List[GeneratedContent]:
    """Core content generation logic with proper content formatting and recipient handling."""
    try:
        # Enhanced prompt for proper content structure
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert content generator for business meetings. Based on the meeting transcription, generate appropriate follow-up content such as emails/messages to be sent post meeting to in meeting participants or external entities, documents to be drafted, or reports ( not meeting summary, as it is already covered).

IMPORTANT FORMATTING REQUIREMENTS:
1. For emails: content should be a PLAIN TEXT STRING formatted as a complete email body
2. For documents: content should be a PLAIN TEXT STRING formatted as a structured document
3. Do NOT use complex nested objects or JSON structures in the content field
4. Keep the content as readable plain text that can be directly used

For each content item you generate:
1. Maintain a professional tone
2. Include relevant details from the meeting
3. Identify who should create/send this content and who should receive it ( do not overlap sender and include him/her in receivers)
4. Structure the content clearly and actionably as plain text
5. Ensure creator and recipient names are matched to specific participants
6. The creator should NOT be included in the recipient list (they're sending the content)

Return your response as a JSON array of content objects. Each content object must have:
- type: string (e.g., "email", "document", "report")
- content: string (PLAIN TEXT - the complete email/document content, NOT a complex object)
- subject: string (subject line for emails, title for documents)
- createdForName: string (name of the person who will be sending/creating this content)
- recipientNames: array of strings (names of recipients who will receive email, excluding the sender, use common sense and do not include the sender in the recipients..if there is no recipients other then sender, then do not generate that content)

Example format for email content:
"Dear Team,\n\nI hope this email finds you well.\n\n[Meeting summary and action items]\n\nBest regards,\n[Sender name]"

Example format for document content:
"Meeting Notes - [Date]\n\n1. Introduction\n[Content]\n\n2. Discussion Points\n[Content]\n\n3. Action Items\n[Content]"

Generate appropriate follow-up content based on the meeting context. Return as JSON array."""),
            ("user", """Please generate follow-up content based on this meeting transcription:

Transcription: {transcription}

Content requirements: {content_details}

Available attendees: {attendees}
Available participants: {participants}

Generate appropriate follow-up content for this meeting. Ensure content is plain text format and recipients exclude the creator. Return as JSON array.""")
        ])

        chain = prompt | llm
        
        response = await chain.ainvoke({
            "transcription": transcription,
            "content_details": content_details,
            "attendees": attendees,
            "participants": participants
        })

        # Parse JSON response
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        try:
            # Clean and extract JSON from response
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Try to find JSON array in the response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                content_data_list = json.loads(json_str)
            else:
                # Try single object and convert to array
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    single_content = json.loads(json_str)
                    content_data_list = [single_content]
                else:
                    content_data_list = json.loads(response_text)
            
            # Ensure we have a list
            if not isinstance(content_data_list, list):
                content_data_list = [content_data_list] if content_data_list else []
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}. Response: {response_text}")
            return []

        # Convert to GeneratedContent objects with proper formatting
        generated_content_list = []
        default_creator = get_default_participant_id(participants)
        
        logger.debug(f"Processing {len(content_data_list)} content items")
        
        for content_data in content_data_list:
            try:
                # Smart matching for creator and recipients
                created_for_name = content_data.get("createdForName", "default")
                recipient_names = content_data.get("recipientNames", [])
                
                # Handle backward compatibility
                if "recipientName" in content_data and not recipient_names:
                    recipient_names = [content_data["recipientName"]]
                
                # Ensure recipient_names is a list
                if not isinstance(recipient_names, list):
                    recipient_names = [recipient_names] if recipient_names else ["default"]
                
                # Match creator ID
                created_for_id = smart_match_participant_id(created_for_name, participants)
                
                # Match recipients but exclude creator
                recipient_emails = smart_match_participant_emails(recipient_names, participants, created_for_id)
                
                # Ensure we never use "ai" if we have valid participants
                if created_for_id == "ai" and participants:
                    created_for_id = default_creator
                if recipient_emails == "ai" and participants:
                    recipient_emails = get_default_participant_email(participants, created_for_id)
                
                # Ensure content is a string, not a complex object
                content_value = content_data.get("content", "")
                if isinstance(content_value, dict):
                    # Convert complex content object to plain text
                    content_parts = []
                    
                    if content_value.get("greeting"):
                        content_parts.append(content_value["greeting"])
                        content_parts.append("")  # Empty line
                    
                    if content_value.get("summary"):
                        for section in content_value["summary"]:
                            if isinstance(section, dict):
                                if section.get("heading"):
                                    content_parts.append(f"{section['heading']}:")
                                if section.get("text"):
                                    if isinstance(section["text"], list):
                                        content_parts.extend(section["text"])
                                    else:
                                        content_parts.append(section["text"])
                                content_parts.append("")  # Empty line
                    
                    if content_value.get("closing"):
                        content_parts.append(content_value["closing"])
                    
                    content_value = "\n".join(content_parts)
                
                logger.debug(f"Content creator name: '{created_for_name}' -> ID: '{created_for_id}'")
                logger.debug(f"Content recipient names: {recipient_names} -> Emails: '{recipient_emails}'")
                logger.debug(f"Content is plain text: {isinstance(content_value, str)}")

                # Create GeneratedContent object with proper formatting
                generated_content = GeneratedContent(
                    organizationId=organization_id,
                    departmentId=department_id,
                    createdForId=created_for_id,
                    type=content_data.get("type", content_details.get("type", "email")),
                    content=content_value,  # Ensure this is a string
                    subject=content_data.get("subject", content_details.get("subject", "Meeting Follow-up")),
                    recipientEmail=recipient_emails  # Excludes creator
                )
                
                generated_content_list.append(generated_content)
                
            except Exception as content_error:
                logger.error(f"Error creating content from data {content_data}: {content_error}")
                continue

        # Always return a list (can be empty)
        if not generated_content_list:
            logger.info("No content was generated from the transcription")
            return []

        # Iterative refinement for the first content item (2 iterations for speed)
        if generated_content_list:
            primary_content = generated_content_list[0]
            
            for i in range(2):
                try:
                    # Critique
                    critique_prompt = ChatPromptTemplate.from_messages([
                        ("system", """You are a professional communication reviewer. Analyze the provided content and provide constructive criticism focusing on:

1. Professional tone and language
2. Completeness and clarity
3. Alignment with the meeting transcription
4. Actionability and usefulness for recipients
5. Appropriate structure and formatting as plain text
6. Correct identification of creator and recipients

Provide specific suggestions for improvement."""),
                        ("user", "Please critique this generated content: {content}")
                    ])
                    
                    critique_chain = critique_prompt | llm
                    critique_response = await critique_chain.ainvoke({
                        "content": primary_content.content
                    })
                    
                    critique = critique_response.content if hasattr(critique_response, 'content') else str(critique_response)

                    # Refine
                    refine_prompt = ChatPromptTemplate.from_messages([
                        ("system", """Based on the critique provided, refine and improve the content. Ensure it is:

1. Professional and well-written
2. Aligned with the meeting transcription
3. Clear and actionable
4. Appropriately structured as PLAIN TEXT
5. Valuable to the recipients

Return the improved content as a JSON object with the same structure. Make sure the content field is a PLAIN TEXT STRING, not a complex object."""),
                        ("user", """Original meeting transcription: {transcription}

Content requirements: {content_details}

Available attendees: {attendees}
Available participants: {participants}

Current content: {current_content}
Critique: {critique}

Please provide the refined content based on this feedback, ensuring it's formatted as plain text.""")
                    ])
                    
                    refine_chain = refine_prompt | llm
                    refine_response = await refine_chain.ainvoke({
                        "transcription": transcription,
                        "content_details": content_details,
                        "attendees": attendees,
                        "participants": participants,
                        "current_content": primary_content.content,
                        "critique": critique
                    })
                    
                    # Parse refined response
                    refine_text = refine_response.content if hasattr(refine_response, 'content') else str(refine_response)
                    
                    try:
                        refine_text = refine_text.strip()
                        if refine_text.startswith('```json'):
                            refine_text = refine_text.replace('```json', '').replace('```', '').strip()
                        elif refine_text.startswith('```'):
                            refine_text = refine_text.replace('```', '').strip()
                        
                        # Try to find JSON object in the response
                        json_match = re.search(r'\{.*\}', refine_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            refined_data = json.loads(json_str)
                            
                            # Update content with refined version, ensure it's a string
                            refined_content = refined_data.get("content", primary_content.content)
                            if isinstance(refined_content, dict):
                                # Convert to plain text if it's still a complex object
                                content_parts = []
                                for key, value in refined_content.items():
                                    if isinstance(value, list):
                                        content_parts.extend(value)
                                    else:
                                        content_parts.append(str(value))
                                refined_content = "\n".join(content_parts)
                            
                            primary_content.content = refined_content
                            if refined_data.get("subject"):
                                primary_content.subject = refined_data.get("subject")
                            
                        else:
                            logger.warning(f"Could not find JSON in refined response for iteration {i+1}")
                            
                    except json.JSONDecodeError as refine_error:
                        logger.warning(f"Failed to parse refined content for iteration {i+1}: {refine_error}")
                    
                except Exception as refinement_error:
                    logger.warning(f"Content refinement iteration {i+1} failed: {refinement_error}. Continuing with current content.")
                    break

        logger.info(f"Generated {len(generated_content_list)} content items with proper formatting")
        return generated_content_list
        
    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")
        return []

async def content_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy node wrapper for backward compatibility"""
    try:
        if not state.get("content_detected"):
            logger.debug("No content detected, skipping content_generation_node")
            return state

        logger.debug("Entering content_generation_node")
        transcription = state.get("transcription", "")
        content_details = state.get("content_details", {})
        attendees = state.get("attendees", [])
        participants = state.get("participants", [])
        organization_id = state.get("organizationId", "")
        department_id = state.get("departmentId")

        generated_content_list = await generate_content(transcription, content_details, attendees, participants, organization_id, department_id)

        # Update state - content should always be a list
        updated_state = state.copy()
        updated_state["generatedContent"] = [content.model_dump() for content in generated_content_list] if generated_content_list else []
        updated_state["messages"] = state.get("messages", []) + ["Content generated and refined"]
        updated_state["status"] = "pending"
        
        logger.info(f"Successfully generated {len(generated_content_list)} content items")
        return updated_state
        
    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")
        error_state = state.copy()
        error_state["status"] = "failure"
        error_state["messages"] = state.get("messages", []) + [f"Content generation failed: {str(e)}"]
        
        # Send SSE error notification
        try:
            send_sse({
                "success": False,
                "message": f"Content generation failed: {str(e)}",
                "status": "failure",
                "data": {}
            }, event="error")
        except Exception as sse_error:
            logger.warning(f"Failed to send SSE error: {sse_error}")
        
        return error_state