import asyncio
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from stagehand import Stagehand, StagehandConfig

# Load environment variables
load_dotenv()

# Define Pydantic models for structured data extraction
class Company(BaseModel):
    name: str = Field(..., description="Company name")
    description: str = Field(..., description="Brief company description")

class Companies(BaseModel):
    companies: list[Company] = Field(..., description="List of companies")

async def main():
    # Create configuration for AWS AgentCore Browser
    config = StagehandConfig(
        env="AWS",  # Use AWS AgentCore Browser
        aws_region=os.getenv("AWS_REGION", "us-west-2"),  # AWS region
        aws_profile=os.getenv("AWS_PROFILE"),  # Optional: AWS profile name
        model_name="google/gemini-2.5-flash-preview-05-20",
        model_client_options={"apiKey": os.getenv("MODEL_API_KEY")},
        verbose=2,  # Set to 2 for detailed logs
    )

    stagehand = Stagehand(config)

    try:
        print("\n🚀 Initializing Stagehand with AWS AgentCore Browser...")
        # Initialize Stagehand
        await stagehand.init()

        print(f"✅ AWS AgentCore Browser session created!")
        print(f"📍 Region: {stagehand.aws_region}")
        if stagehand.aws_session_id:
            print(f"🔑 Session ID: {stagehand.aws_session_id}")

        page = stagehand.page

        print("\n🌐 Navigating to aigrant.com...")
        await page.goto("https://www.aigrant.com")

        print("\n📊 Extracting company data...")
        # Extract companies using structured schema
        companies_data = await page.extract(
          "Extract names and descriptions of 5 companies in batch 3",
          schema=Companies
        )

        # Display results
        print("\n✨ Extracted Companies:")
        for idx, company in enumerate(companies_data.companies, 1):
            print(f"  {idx}. {company.name}: {company.description}")

        print("\n🔍 Observing Browserbase link...")
        observe = await page.observe("the link to the company Browserbase")
        print(f"Observe result: {observe}")

        print("\n🖱️  Clicking Browserbase link...")
        act = await page.act("click the link to the company Browserbase")
        print(f"Act result: {act}")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise
    finally:
        # Close the client
        print("\n🔒 Closing Stagehand and AWS AgentCore Browser session...")
        await stagehand.close()
        print("✅ Session closed successfully!")

if __name__ == "__main__":
    # Note: AWS AgentCore Browser requires:
    # 1. AWS credentials configured (via AWS CLI, environment variables, or IAM role)
    # 2. bedrock-agentcore package installed: pip install stagehand[aws]
    # 3. AWS_REGION environment variable set (e.g., us-west-2, us-east-1)
    # 4. Appropriate IAM permissions for AgentCore Browser

    print("=" * 60)
    print("AWS AgentCore Browser Example")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  - AWS credentials configured")
    print("  - bedrock-agentcore installed (pip install stagehand[aws])")
    print("  - AWS_REGION environment variable set")
    print("  - MODEL_API_KEY environment variable set")
    print("=" * 60)

    asyncio.run(main())
