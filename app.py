#!/usr/bin/env python3
import aws_cdk as cdk
from infra.stack import QuizSystemStack

app = cdk.App()
QuizSystemStack(app, "QuizSystemStack")
app.synth()
