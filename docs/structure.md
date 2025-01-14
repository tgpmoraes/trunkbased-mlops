# Project structure

This repository has an specific structure where each folder has an intended audience.

## General structure

The repository contains the follwing structure. Some folders are specific to this model we are showcasing and hence if you plan to use this template you will have to change them. They are mark with * stars * for your convenience.

```
── .azure-pipelines                                 # Azure DevOps CI/CD
│   └── templates                                      # Azure DevOps templates
├── .cloud                                          # Infrastructure as code
│   ├── dev                                             # Dev parameters
│   └── templates                                       # ARM templates
├── .github                                         # GitHub Actions CI/CD
│   ├── actions                                         # GHA custom actions
│   └── workflows                                       # GHA workflows
├── datasets                                        # Datasets configuration
│   ├── *portuguese-hate-speech-tweets*                   # Training dataset
│   │   └── data                                            # Initial data
│   └── *portuguese-hate-speech-tweets-eval*              # Evaluation dataset
│       └── data                                            # Initial data
├── docs                                            # Documentation
├── endpoints                                       # Azure ML endpoints
│   └── *hate-pt-speech*                                  # Rest service for the model
│       └── deployments                                     # Hate detection deployments (only one: main)
├── environments                                    # Azure ML environments
│   ├── *transformers-torch-19*                           # Environment for inference
│   └── *transformers-torch-19-dev*                       # Environment for training and dev
├── jobs                                            # Azure ML Job definitions
│   └── *hatedetection*                                   # Jobs for the hate dection model, including params
├── notebooks                                       # Experimentation notebooks
└── src                                             # Model's source code
    ├── *common*                                          # Common library to speed up development
    │   ├── datasets
    │   ├── jobs
    │   └── models
    ├── *hatedetection*                               # Hate detection model
    │   ├── model                                       # PyTorch model implementation
    │   ├── prep                                        # Data preparation code
    │   ├── score                                       # Inference code
    │   └── train                                       # Training code
    └── tests                                       # Unit tests
        └── *hatedetection*                               # Tests specific for model hate detection
            └── scoring
```

## Details

| Folder              | Description | Owner | Collaborate |
|------------------------|-------------------------------------------------------------------|---------------------|-------|
| .cloud                | Contains the `ARM` templates to deploy resources as IaC. There will be one folder per each environment, for instance `dev`, `qa` and `prd`. The subfolder `templates` is intended to have generic `ARM` templates that then each environment can configure depending on requirements. | Cloud Architects | ML Engineer |
| .azure-pipelines      | Contains the CI/CD implementation for Azure DevOps. | ML/DevOps Engineer | |
| .github               | Contains the CI/CD implementation for GitHub Actions. | ML/DevOps Engineer | |
| endpoints            | Contains the definitions of all the REST services that will be deployed from registered models | ML Engineers | |
| datasets             | Contains the definitions of all the datasets that will be used by the project. | ML Engineer | Data Scientist |
| environments         | Contains the definitions of all the training and inference environments that developers/data scientist can use | ML Engineer | Data Scientist |
| jobs                 | Contains the definitions of all the jobs that you want to submit to Azure ML | Data Scientist | ML Engineer |
| notebooks            | Contains all the notebooks for interactive development of models and experimentation | Data Scientist | NA |
| src                  | Contains the source code for running training and inference routines in models | Data Scientist | NA |