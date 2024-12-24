import os, boto3, json
from botocore.config import Config

def _get_clients():
    args = {'region_name': os.getenv("AWS_REGION", "us-west-2")}
    if not os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        args.update(aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                   aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
    
    s = boto3.Session()
    runtime_args = args.copy()
    runtime_args['config'] = Config(read_timeout=300, connect_timeout=300, retries={'max_attempts': 0})
    return s.client('bedrock', **args), s.client('bedrock-runtime', **runtime_args)

bedrock, runtime = _get_clients()
MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"

def generate_stream(messages, max_gen_len=1024, temperature=0.9):
    try:
        response = runtime.converse_stream(
            modelId=MODEL_ID,
            messages=[{"role": m["role"], "content": [{"text": m["content"]}]} 
                     for m in messages if m["role"] != "system"],
            system=[{"text": m["content"]} for m in messages if m["role"] == "system"],
            inferenceConfig={"maxTokens": max_gen_len, "temperature": temperature}
        )
        
        for e in response.get('stream', []):
            if text := e.get('contentBlockDelta', {}).get('delta', {}).get('text', ''):
                # Properly serialize the JSON response
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
        print(f"Generation error: {str(e)}")  # Log the actual error
        yield 'data: [ERROR]\n\n'

if __name__ == "__main__":
    if bedrock.get_foundation_model(modelIdentifier=MODEL_ID).get('modelDetails', {}).get('responseStreamingSupported'):
        for o in generate_stream([
            {"role": "user", "content": "Tell me a joke about computers."},
            {"role": "system", "content": "Be helpful and humorous."}
        ]): print(o, end='', flush=True)