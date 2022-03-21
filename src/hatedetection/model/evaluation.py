import logging
from typing import Dict, Any
import torch
import mlflow
import numpy as np
import math
from sklearn.metrics import f1_score, precision_score, confusion_matrix
from sklearn.metrics import accuracy_score, recall_score, precision_recall_fscore_support
from statsmodels.stats.contingency_tables import mcnemar

import common.models.model_management as amlmodels
from hatedetection.prep.text_preparation import load_examples 
from hatedetection.model.hate_detection_classifier import HateDetectionClassifier

def compute_classification_metrics(pred: Dict) -> Dict[str, float]:
    """
    Computes the metrics given predictions of a torch model

    Parameters
    ----------
    pred: Dict
        Predictions returned from the model.

    Returns
    -------
    Dict[str, float]:
        The metrics computed, inclusing `accuracy`, `f1`, `precision`, `recall` and `support`.
    """
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    acc = accuracy_score(labels, preds)
    precision, recall, f1, support = precision_recall_fscore_support(labels, preds, average='weighted')
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall,
        'support': support
    }

def resolve_and_compare(model_name: str, champion: str, challenger: str, eval_dataset: str, confidence: float = 0.05) -> Dict[str, Dict[str, float]]:
    """
    Resolves the model from it's name and runs the evaluation routine.

    Parameters
    ----------
    model_name: str
        Name of the model to get. The model will be downloaded from the model registry.
    champion: str
        Champion version of the model. This can be a number, a tag like `stage=production` or `latest`
    challenger: str
        Challenger version of the model. This can be a number, a tag like `stage=production` or `latest`
    eval_dataset: str
        Path that leads to the dataset.
    confidence: float
        The condifidence level of the test (p-value). Defaults to 95% (0.05)

    Returns
    -------
    Dict[str, float]
       A dictionary containing the keys `statistic`, `pvalue` as a result of the statistical test.
    """
    champion_path = amlmodels.resolve_model_from_context(model_name, version=champion, target_path="champion")
    challenger_path = amlmodels.resolve_model_from_context(model_name, version=challenger, target_path="challenger")

    return compute_mcnemmar(champion_path, challenger_path, eval_dataset, confidence)

def predict_batch(model, data, batch_size = 64):
    sample_size = len(data)
    batches_idx = range(0, math.ceil(sample_size / batch_size))
    scores = np.zeros(sample_size)

    for batch_idx in batches_idx:
        batch_from = batch_idx * batch_size
        batch_to = batch_from + batch_size
        scores[batch_from:batch_to] = model.predict(data.iloc[batch_from:batch_to].to_frame("text"))['hate']
    
    return scores

def compute_mcnemmar(champion_path: str, challenger_path: str, eval_dataset: str, confidence: float = 0.05) -> Dict[str, Dict[str, Any]]:
    """
    Compares two hate detection models and decides if the two models make the same mistakes or not.
    Note that this method doesn't tell if challenger is better that champion but if the models are
    statistically different. It uses the McNemmar test.

    Parameters
    ----------
    champion_path: str
        Path to the champion model.
    challenger_path: str
        Path to the challenger model.
    eval_dataset: str
        Path to the evaluation dataset.
    confidence: float
        The condifidence level of the test (p-value). Defaults to 95% (0.05)

    Returns
    -------
    Dict[str, Dict[str, float]]:
        A dictionary containing the keys `statistic`, `pvalue` as a result of the statistical test.
    """
    mlflow.log_param("test", "mcnemar")
    mlflow.log_param("confidence", confidence)

    if champion_path and challenger_path:
        text, _ = load_examples(eval_dataset)
        champion_model = mlflow.pyfunc.load_model(champion_path)
        champion_scores = predict_batch(champion_model, text)

        logging.info("[INFO] Unloading champion object from memory")
        del champion_model
        torch.cuda.synchronize()

        challenger_model = mlflow.pyfunc.load_model(challenger_path)
        challenger_scores = predict_batch(challenger_model, text)

        logging.info("[INFO] Unloading challenger object from memory")
        del challenger_model
        torch.cuda.synchronize()

        cont_table = confusion_matrix(champion_scores, challenger_scores)
        results = mcnemar(cont_table, exact=False)

        metrics = {
            "statistic": results.statistic,
            "pvalue": results.pvalue,
        }

    else:
        metrics = {
            "statistic": 0,
            "pvalue": 0,
        }
        mlflow.log_param("warning", "No champion model indicated")

    mlflow.log_metrics(metrics)
    return metrics

def resolve_and_evaluate(model_name: str, eval_dataset: str, threshold: float = 0.5) -> Dict[str, float]:
    """
    Resolves the model from it's name and runs the evaluation routine.

    Parameters
    ----------
    model_name: str
        Name of the model to get. The model will be downloaded from the model registry.
    eval_dataset: str
        Path that leads to the dataset.
    threshold: float
        The workspace to load the model from.
        If not indicated, it will use the default model.

    Returns
    -------
    Dict[str, float]
       A dictionary containing the keys `f1_score`, `precision`, `recall`, `specificity` and `accuracy` as the results of the run.
    """
    model_path = amlmodels.resolve_model_from_context(model_name, "latest")
    
    return evaluate(model_path, eval_dataset, threshold)

def evaluate(model_path: str, eval_dataset: str, threshold: float = 0.5) -> Dict[str, Dict[str, float]]:
    """
    Evaluation routine for the model
    
    Parameters
    ----------
    model_path: str
        Path to where the model is stored.
    eval_dataset: str
        Path that leads to the dataset.
    threshold: float
        The workspace to load the model from.
        If not indicated, it will use the default model.

    Returns
    -------
    Dict[str, Dict[str, float]]
       A dictionary of "metrics" containing the keys `f1_score`, `precision`, `recall`, `specificity`
       and `accuracy` as the results of the run.
    """
    # Get the path for the dataset from the input
    text, labels = load_examples(eval_dataset)
    model = HateDetectionClassifier()
    model.load(model_path)

    # Runs the model and transform the results into binaries according to the threshold
    scores     = model.predict_proba(model_input=text)
    bin_scores = [1 if score > threshold else 0 for score in scores]

    tn, fp, _, _ = confusion_matrix(labels, bin_scores).ravel()

    # Metrics
    f1 = f1_score(labels, bin_scores)
    precision = precision_score(labels, bin_scores)
    recall = recall_score(labels, bin_scores)
    specificity = tn / (tn+fp) if (tn+fp) != 0 else 0
    accuracy = accuracy_score(labels, bin_scores)

    # Output a dict with the calculated metrics
    metrics = {
        "f1_score": f1,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "accuracy": accuracy
    }

    return {'metrics': metrics}
