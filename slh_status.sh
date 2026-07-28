#!/bin/bash
echo "SLH STATUS"
slh doctor
railway logs --tail 20
railway variables | grep -E "BOT_TOKEN|GROQ"
