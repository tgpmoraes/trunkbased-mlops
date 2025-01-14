"""
Model management capabilities from Azure ML
"""

import os
import logging
from typing import Any, List, Dict
from os import PathLike

import azureml.core as aml
from azureml.exceptions import RunEnvironmentException, ModelNotFoundException, WebserviceException
from azureml.core.authentication import AzureCliAuthentication
from common.datasets.dataset_management import get_dataset

def download_model_from_context(model_name: str, version: str = None,
                               target_path: PathLike = '.', **tags) -> os.PathLike:
    """
    Resolves the name of a given model registered in Azure ML and downloads it in a local
    directory ready to be used. This method can resolve the model either when working inside
    of an Azure ML run or inside of an Azure ML compute.

    Parameters
    ----------
    model_name: str
        The name of the model to use. Model can also indicate the version in the format
        <model_name>:<model_version>. If so, `version` is ignored.
    version: str
        The version of the model. Version can be a number, a token like "latest" or a tag in
        the form <tag>=<tag_value>.
    target_path: PathLike
        The target path where the model should be placed. Defaults to current directory
    """
    try:
        run = aml.Run.get_context(allow_offline=False)
        workspace = run.experiment.workspace
    except RunEnvironmentException:
        logging.warning("[WARN] Running outside of AML context. Trying to get workspace \
            from config.")
        workspace = aml.Workspace.from_config()

    model = get_model(workspace, model_name, version, **tags)
    if model:
        os.makedirs(target_path, exist_ok=True)
        return model.download(target_dir=target_path, exist_ok=True)

    return None

def get_model(workspace: aml.Workspace, model_name: str, version: str = None, **tags) -> aml.Model:
    """
    Gets a model from the Azure Registry. `model_name` can be the name of the model,
    including it's version. use `[model_name]:[version]` or `[model_name]:latest` or
    `[model_name]:[tag]=[value]`

    Parameters
    ----------
    workspace: aml.Workspace
        Azure ML Workspace
    model_name: str
        Name of the model. It can include the model version.
    version: str
        Version of the model. If indicated in `model_name`, this parameter is ignored.
    tags: kwargs
        Tags the model should contain in order to be retrieved. If tags are indicated in
        model_name, this parameter is ignored.

    Return
    ------
    aml.Model
        The model if any
    """
    tags_list = None

    if ":" in model_name:
        stripped_model_name, version = model_name.split(':')
    else:
        stripped_model_name = model_name

    if version is None or version == "latest":
        model_version = None
    elif version == "current":
        raise ValueError("Model version 'current' is not support using this SDK right now.")
    elif '=' in version:
        model_version = None
        tags_list = [ version ]
    else:
        model_version = int(version)

    if tags:
        if tags_list:
            logging.warning("[WARN] Indicating tags both in version and tags keywords is not supported. Tags are superseded by version.")
        else:
            tags_list = [ f'{tag[0]}={tag[1]}' for tag in tags.items() ]

    try:
        model = aml.Model(workspace=workspace,
                          name=stripped_model_name,
                          version=model_version,
                          tags=tags_list)

        if model:
            logging.info(f"[INFO] Returning model with name: {model.name}, version: {model.version}, tags: {model.tags}")

        return model

    except ModelNotFoundException:
        logging.warning(f"[WARN] Unable to find a model with the given specification. \
            Name: {stripped_model_name}. Version: {model_version}. Tags: {tags}.")
    except WebserviceException:
        logging.warning(f"[WARN] Unable to find a model with the given specification. \
            Name: {stripped_model_name}. Version: {model_version}. Tags: {tags}.")

    logging.warning(f"[WARN] Unable to find a model with the given specification. \
            Name: {stripped_model_name}. Version: {model_version}. Tags: {tags}.")
    return None


def get_metric_for_model(workspace: aml.Workspace,
                         model_name: str,
                         version: str,
                         metric_name: str,
                         model_hint: str = None) -> Any:
    """
    Gets a given metric from the run that generated a given model and version.

    Parameters
    ----------
    workspace: azureml.core.Workspace
        The workspace where the model is stored.
    model_name: str
        The name of the model registered
    version: str
        The version of the model. It can be a number like "22" or a token like "latest" or a tag.
    metric_name: str
        The name of the metric you want to retrieve from the run
    model_hint: str | None
        Any hint you want to provide about the given version of the model. This is useful for
        debugging in case the given metric you indicated is not present in the run that generated
        the model.

    Return
    ------
        The value of the given metric if present. Otherwise an exception is raised.
    """
    model_run = get_run_for_model(workspace, model_name, version)
    if model_run:
        model_metric = model_run.get_metrics(name=metric_name)

        if metric_name not in model_metric.keys():
            raise ValueError(f"Metric with name {metric_name} is not present in \
                run {model_run.id} for model {model_name} ({model_hint}). Avalilable \
                metrics are {model_run.get_metrics().keys()}")

        metric_value = model_metric[metric_name]

        if isinstance(metric_value, list):
            return metric_value[0]

        return metric_value

    logging.warning("[WARN] No model matches the given specification. No metric is returned")
    return None

def get_run_for_model(workspace: aml.Workspace,
                      model_name: str, version: str = 'latest', **tags) -> aml.Run:
    """
    Gets a the run that generated a given model and version.

    Parameters
    ----------
    workspace: azureml.core.Workspace
        The workspace where the model is stored.
    model_name: str
        The name of the model registered
    version: str
        The version of the model. It can be a number like "22" or a token like "latest" or a tag.

    Return
    ------
        The given run.
    """
    model = get_model(workspace, model_name, version, **tags)
    if model:
        if not model.run_id:
            raise ValueError(f"The model {model_name} has not a run associated with it. \
                Unable to retrieve metrics.")

        return workspace.get_run(model.run_id)

    return None

def register(subscription_id: str, resource_group: str, workspace_name:str, name: str,
             version: str, model_path: str, description: str, run_id: str = None,
             datasets_id: List[str] = None, tags: Dict[str, Any] = None):
    """
    Registers a model into the model registry using the given parameters. This method
    requires Azure CLI Authentication.
    """
    cli_auth = AzureCliAuthentication()
    ws = aml.Workspace(subscription_id, resource_group, workspace_name, auth=cli_auth)

    if version:
        logging.warning(f"[WARN] Model version {version} parameter is only for backward`\
         compatibility. Latest is used.")

    if datasets_id:
        datasets = [get_dataset(workspace=ws, name=ds) for ds in datasets_id]
    else:
        datasets = None

    if run_id:
        logging.info(f"[INFO] Looking for run with ID {run_id}.")

        try:
            model_run = aml.Run.get(ws, run_id)
        except RuntimeError:
            model_run = None

        if model_run:
            model_run.register_model(model_name=name,
                                     model_path=model_path,
                                     description=description,
                                     tags=tags,
                                     datasets=datasets)
        else:
            logging.error(f"[ERROR] Run with ID {run_id} couldn't been found. \
                Model is not registered.")
    else:
        aml.Model.register(workspace=ws,
                           model_name=name,
                           description=description,
                           model_path=model_path,
                           tags=tags,
                           datasets=datasets)
