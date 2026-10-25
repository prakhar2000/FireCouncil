# AWS setup — Tuesday Oct 20

MVP account setup in `us-east-2`. This account is limited to that region. The hack requires OpenCV 5 and a meaningful piece on AWS. It does not require the COOL image.

OpenCV for this build is the normal PyPI package, installed on your laptop. See [TODAY_CODE.md](TODAY_CODE.md). COOL is a later switch, after the replay works and you choose to spend credits. The vision code keeps using `import cv2`, so that switch does not rewrite the detectors.

Tonight uses three services:

| Service | Job |
|---|---|
| **AWS Budgets** | Email you at 50%, 80%, and 100% of a monthly cap. |
| **Amazon Bedrock** | The fast model for the specialists and the stronger model for the planner. Your laptop calls it with the credentials from `aws configure`. |
| **Amazon S3** | One private bucket for evidence images and replay frames. |

No EC2 instance tonight. The COOL Marketplace image and the Graviton server are what spend the credits, so they stay at the bottom of this file.

Decisions, residents, and the off switch stay in local files (`.env` and `data/local/`).

Leave these out of the MVP: the COOL server, DynamoDB, SSM Parameter Store, Lambda, API Gateway, CloudFront, Cognito, Step Functions, EventBridge, SQS, SNS, SMS, Polly, ECR, and CDK. SES is optional after the replay works.

None of these values go in git: account id, FIRMS key, model ids. `.env` is gitignored.

## Done when

- [ ] Budget alarms exist at 50%, 80%, and 100%.
- [ ] Bedrock in `us-east-2` shows access for one fast model and one stronger model. Their ids are in `.env` only.
- [ ] Bucket `firecouncil-<account>-data` exists in `us-east-2`, private, with `raw/` expiring after 14 days.
- [ ] No EC2 instance is running.

## 0. CLI and region

```bash
aws sts get-caller-identity
aws configure get region
```

The identity call must succeed. Then force the region for this shell:

```bash
export AWS_REGION=us-east-2
export AWS_DEFAULT_REGION=us-east-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export FC_BUCKET=firecouncil-${AWS_ACCOUNT_ID}-data
echo "$AWS_ACCOUNT_ID"
echo "$FC_BUCKET"
```

Remember the account id. It is part of the bucket name. Do not commit it.

If the CLI has no credentials, run `aws configure` with an IAM user that can create a bucket and turn on Bedrock models. Billing alarms sometimes require the account root or an IAM user with billing access. If a budget step returns `AccessDenied`, turn on **IAM user and role access to billing information** as root, then retry.

Public GOES files stay in `s3://noaa-goes18` in `us-east-1`. That bucket is not yours. Read it later with `--region us-east-1 --no-sign-request`. Everything you create is in `us-east-2`.

## 1. Budgets first

Console: [Billing → Budgets](https://console.aws.amazon.com/billing/home#/budgets).

1. Create a budget → **Customize (advanced)** → **Cost budget**.
2. Name: `firecouncil-monthly`.
3. Period: **Monthly**. Amount: the credits you actually have. If you do not know yet, use **50 USD** and lower it once you see the real credit balance.
4. Add three alerts, actual cost, at **50%**, **80%**, and **100%**. Send each one to your email.
5. Create the budget and confirm the three alert rows exist.

## 2. Bedrock model access

Console, region **US East (Ohio)**: [Bedrock model access](https://us-east-2.console.aws.amazon.com/bedrock/home?region=us-east-2#/modelaccess).

1. Confirm the region in the console is **Ohio / us-east-2**.
2. Enable one **fast** model for the three specialists.
3. Enable one **stronger** model for the planner.
4. If a use-case form appears, submit it now. Approval can lag. Local code does not wait on it. The orchestrator still emits a decision with rules alone.
5. Copy both **model ids** into `.env` as `PERSONA_MODEL_ID` and `PLANNER_MODEL_ID`.

Use the Bedrock runtime (`InvokeModel`). Leave **Bedrock Agents** unused.

## 3. S3 bucket

`us-east-2` needs a location constraint. `us-east-1` does not, and this account cannot create the bucket there.

```bash
aws s3api create-bucket \
  --bucket "$FC_BUCKET" \
  --region us-east-2 \
  --create-bucket-configuration LocationConstraint=us-east-2

aws s3api put-public-access-block \
  --bucket "$FC_BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-encryption \
  --bucket "$FC_BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
```

Expire raw camera frames after 14 days. Evidence objects live outside `raw/`, so this rule leaves them in place.

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$FC_BUCKET" \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "expire-raw",
      "Filter": {"Prefix": "raw/"},
      "Status": "Enabled",
      "Expiration": {"Days": 14}
    }]
  }'

aws s3 ls | grep firecouncil
```

## 4. FIRMS key

Request a free key: https://firms.modaps.eosdis.nasa.gov/api/map_key/

When the email arrives, put the key in `.env` as `FIRMS_MAP_KEY`. Leave it blank until then. Local tests do not call FIRMS.

## 5. Local env file

In the repo root, create `.env` yourself. Do not commit it.

```bash
AWS_REGION=us-east-2
FC_BUCKET=firecouncil-YOUR_ACCOUNT_ID-data
FIRMS_MAP_KEY=
WATCH_BBOX=-120.5,32.5,-114.0,35.5
PERSONA_MODEL_ID=
PLANNER_MODEL_ID=
VISION_URL=http://localhost:8080
ACK_WINDOW_SECONDS=60
KILL_SWITCH=false
```

Fill the bucket name and the two model ids. Leave the model ids and the FIRMS key blank if they are still pending.

## After the replay works

**SES.** One real email is a strong moment in the video. Verify your inbox and the caregiver inbox in the [SES console for us-east-2](https://us-east-2.console.aws.amazon.com/ses/home?region=us-east-2#/identities), stay in the sandbox, and send only to those verified addresses. Until then, the app writes the message to `data/local/outbox.jsonl`.

**COOL, when you decide to spend the credits.** Subscribe to [Cloud Optimized OpenCV for AWS Graviton4](https://aws.amazon.com/marketplace/pp/prodview-fdvbfiewzuehs) and launch one `c8g.2xlarge` in `us-east-2`. The 7-day software trial turns into a paid fee on its own, on top of the EC2 hourly price. On that host, `cv2` comes from `/opt/cool/venvs/python_3.12`. Do not pip-install OpenCV there. Run the same vision code, save `cv2.__version__`, `cv2.__file__`, and `platform.machine()` to `docs/cool_verify.txt`, then stop the instance. That file is the COOL award evidence. The laptop keeps the PyPI package.

## If something blocks

| What happened | What to do |
|---|---|
| Budget access denied | Use root once to allow IAM billing access, then retry. Keep coding. |
| A call fails because the region is `us-east-1` | Repeat it with `--region us-east-2`. This account cannot create resources in `us-east-1`. |
| Bedrock form still pending | Leave the model ids blank. The local orchestrator uses rules only. |
| Bucket name already taken | Add a short suffix, such as `firecouncil-<account>-data-1`, and use that name in `.env`. |
