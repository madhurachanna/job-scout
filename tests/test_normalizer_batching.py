import unittest
from unittest.mock import MagicMock, patch
import json
from agents.normalizer import normalizer_agent
from models.state import AgentState

class TestNormalizerBatching(unittest.TestCase):
    @patch("agents.normalizer.ChatOpenAI")
    def test_batching_logic(self, mock_chat_openai):
        # Mock LLM instance and invoke method
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # Create a large list of 25 dummy jobs
        extracted_jobs = [{"title": f"Job {i}", "company": "Test Co", "location": "Remote"} for i in range(25)]
        
        # State input
        state = {
            "extracted_jobs": extracted_jobs,
            "current_page": {"name": "Test Source", "url": "http://test.com"},
        }
        
        # Mock LLM responses for each batch
        # We expect 3 batches: 10, 10, 5
        def side_effect(messages):
            # Extract the user prompt content to check batch size
            user_content = messages[1].content
            # The prompt contains json dump of jobs
            # We can just return a valid JSON response based on what was sent, or just dummy
            # But wait, the agent logic parses the return.
            # Let's see what batch is being processed by inspecting the prompt?
            # Or just return a generic list of "Normalized Job X"
            
            # Simple approach: Return whatever was passed in, but normalized
            # This requires parsing the input JSON from the prompt string
            import re
            json_str = user_content.split("Raw job data:\n")[1].split("\n\nReturn ONLY")[0]
            jobs = json.loads(json_str)
            
            normalized_jobs = []
            for job in jobs:
                normalized_jobs.append({
                    "title": job["title"],
                    "company": "Test Co Normalized",
                    "location": "Remote, Earth",
                    "url": "http://test.com/job",
                    "description": "A job",
                    "date_posted": "2023-01-01",
                    "source": "Test Source",
                    "job_type": "Full-time"
                })
            
            return MagicMock(content=json.dumps(normalized_jobs))

        mock_llm.invoke.side_effect = side_effect
        
        # Run the agent
        result = normalizer_agent(state)
        
        # Verification
        self.assertEqual(len(result["normalized_jobs"]), 25)
        self.assertEqual(mock_llm.invoke.call_count, 3) # Should be called 3 times (10 + 10 + 5)
        
        # Verify call arguments to ensure batches were correct size
        # Call 1
        args1, _ = mock_llm.invoke.call_args_list[0]
        content1 = args1[0][1].content
        self.assertIn('"Job 0"', content1)
        self.assertIn('"Job 9"', content1)
        self.assertNotIn('"Job 10"', content1)
        
        # Call 2
        args2, _ = mock_llm.invoke.call_args_list[1]
        content2 = args2[0][1].content
        self.assertIn('"Job 10"', content2)
        self.assertIn('"Job 19"', content2)
        
        # Call 3
        args3, _ = mock_llm.invoke.call_args_list[2]
        content3 = args3[0][1].content
        self.assertIn('"Job 20"', content3)
        self.assertIn('"Job 24"', content3)
        
        print(f"\n✅ Test passed: Processed {len(result['normalized_jobs'])} jobs in {mock_llm.invoke.call_count} batches.")

if __name__ == "__main__":
    unittest.main()
