import boto3
import json
import logging
from botocore.config import Config
from botocore.exceptions import ProfileNotFound

# Initialize Uvicorn logger
logger = logging.getLogger("uvicorn")

def _get_clients():
    """Initialize Bedrock clients with appropriate configuration."""
    runtime_config = Config(
        region_name='us-west-2',  # Always use us-west-2 for Bedrock
        read_timeout=300,
        connect_timeout=300,
        retries={'max_attempts': 0}
    )
    
    try:
        # Try to use bedrock profile first
        session = boto3.Session(profile_name='bedrock')
    except ProfileNotFound:
        # Fall back to default credentials (IAM role or default profile)
        session = boto3.Session()
        
    return (
        session.client('bedrock', config=runtime_config),
        session.client('bedrock-runtime', config=runtime_config)
    )

bedrock, runtime = _get_clients()
MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"

def generate_stream(messages, max_gen_len=1024, temperature=0.9):
    """Generate streaming responses from Bedrock."""
    try:
        response = runtime.converse_stream(
            modelId=MODEL_ID,
            messages=[{"role": m["role"], "content": [{"text": m["content"]}]}
                     for m in messages if m["role"] != "system"],
            system=[{"text": m["content"]}
                   for m in messages if m["role"] == "system"],
            inferenceConfig={
                "maxTokens": max_gen_len,
                "temperature": temperature
            }
        )
        
        for event in response.get('stream', []):
            text = event.get('contentBlockDelta', {}).get('delta', {}).get('text', '')
            if text:
                chunk = {
                    "choices": [{
                        "delta": {
                            "content": text
                        }
                    }]
                }
                yield f'data: {json.dumps(chunk)}\n\n'
                
        yield 'data: [DONE]\n\n'
        
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        yield 'data: [ERROR]\n\n'

if __name__ == "__main__":
    if bedrock.get_foundation_model(modelIdentifier=MODEL_ID).get('modelDetails', {}).get('responseStreamingSupported'):
        for o in generate_stream([
            {"role": "user", "content": "Tell me a joke about computers."},
            {"role": "system", "content": "Be helpful and humorous."}
        ]):
            print(o, end='', flush=True)
