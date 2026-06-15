"""
Agent Client - Handles interaction with the Microsoft Foundry agent.

This module contains the core logic for connecting to and communicating with
the agent published in Microsoft Foundry. It uses the OpenAI Responses API
to submit prompts and handle responses.
"""

import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

# Import Azure Identity and OpenAI client libraries
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class AgentClient:
    """Client for interacting with a Microsoft Foundry agent."""
    
    def __init__(self):
        """Initialize the agent client with authentication and endpoint."""
        raw_endpoint = os.getenv("AGENT_ENDPOINT") or ""
        self.agent_endpoint = raw_endpoint.replace("/v4/responses", "") if raw_endpoint else ""
        if not self.agent_endpoint:
            raise ValueError("AGENT_ENDPOINT not found in environment variables")
        
        # Create OpenAI client authenticated with Azure credentials 
        self.client = OpenAI(
            api_key=get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://ai.azure.com/.default"
            ),
            base_url=self.agent_endpoint,
            default_query={"api-version": "2025-11-15-preview"}
        )

        # Maintain chat conversation history (last 3 user exchanges plus a single language instruction)
        # Note: Foundry only accepts 'user' and 'assistant' roles, so we use a user instruction message.
        self.conversation_history: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    "Eres un asistente que responde siempre en español. "
                    "No devuelvas JSON ni estructuras a menos que el usuario lo pida expresamente. "
                    "Contesta las dudas en español."
                )
            }
        ]
        self.max_history = 3
    
    def send_message(self, user_message: str) -> str:
        """
        Send a chat message to the agent and return the response.

        Args:
            user_message: The text message from the user

        Returns:
            The agent's response text
        """
        return self.send_prompt(user_message, add_to_history=True)

    def send_prompt(self, prompt: str, add_to_history: bool = False) -> str:
        """
        Send a prompt to the agent and optionally add it to chat history.

        Args:
            prompt: The prompt text.
            add_to_history: Whether to store the prompt in the ongoing chat history.

        Returns:
            The agent's response text.
        """
        request_history = self.conversation_history if add_to_history else [{"role": "user", "content": prompt}]

        if add_to_history:
            self.conversation_history.append({"role": "user", "content": prompt})

        try:
            response = self.client.responses.create(
                input=request_history
            )

            assistant_message = getattr(response, 'output_text', None) or getattr(response, 'text', '')

            if add_to_history:
                self.conversation_history.append({"role": "assistant", "content": assistant_message})
                self._trim_history()

            return assistant_message
        except Exception as e:
            logger.exception("Error communicating with agent")
            return "An internal error occurred while communicating with the agent."

    def _trim_history(self):
        """Keep only the most recent chat exchanges plus the initial instruction."""
        # Preserve the first instruction message at index 0.
        while True:
            user_indices = [i for i, msg in enumerate(self.conversation_history) if msg.get("role") == "user"]
            actual_user_indices = [i for i in user_indices if i != 0]
            if len(actual_user_indices) <= self.max_history:
                break

            first_user = actual_user_indices[0]
            self.conversation_history.pop(first_user)
            if first_user < len(self.conversation_history) and self.conversation_history[first_user].get("role") == "assistant":
                self.conversation_history.pop(first_user)
    
    def reset_conversation(self):
        """Clear the conversation history."""
        self.conversation_history = []
