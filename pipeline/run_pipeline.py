"""CLI del pipeline CRISP-DM: `python -m pipeline.run_pipeline [--patients N] [--export-submission]`."""

from __future__ import annotations

import argparse
import json

from pipeline import despliegue
from pipeline.config import RESULTS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline CRISP-DM de RISA Signal (RISA Data V1.0)")
    parser.add_argument("--patients", type=int, default=None, help="Limitar a los primeros N pacientes (debug rápido, no usa caché)")
    parser.add_argument("--export-submission", action="store_true", help="Escribir signals.csv y evidence.csv en pipeline/data/results/")
    parser.add_argument("--rebuild", action="store_true", help="Ignorar el caché en pipeline/data/cache/ y reprocesar RISA Data V1.0")
    args = parser.parse_args()

    if args.patients:
        result = despliegue.build_dataset(max_patients=args.patients)
    else:
        result = despliegue.load_or_build(force=args.rebuild)

    print(f"Origen de datos: {result.origin}")
    print(f"Pacientes: {len(result.patients)}")
    print(f"Filas vitals (ancho): {len(result.vitals_wide)} · labs: {len(result.labs_long)}")
    counts: dict[str, int] = {}
    for d in result.alert_drafts:
        counts[d.level] = counts.get(d.level, 0) + 1
    print("Distribución de niveles:", counts)

    anomaly_chosen = result.evaluation["anomaly_model"]["chosen_model"]
    pattern_chosen = result.evaluation["pattern_model"]["chosen_model"]
    print(f"\nAnomaly Model elegido (mejor F1 en validación cruzada): {anomaly_chosen}")
    print(f"Pattern Model elegido (mejor F1 en validación cruzada): {pattern_chosen}")
    print("Persistidos en: pipeline/data/model/{anomaly,pattern}_model_best.joblib")

    print("\nComparación de modelos (validación cruzada + test, etiqueta débil, matriz de confusión incluida):")
    print(json.dumps(result.evaluation, indent=2, ensure_ascii=False))
    print("\nCalidad de datos (resumen):")
    print(json.dumps({k: v for k, v in result.quality_report.items() if k != "vital_signs_cleaning"}, indent=2, ensure_ascii=False, default=str))

    if args.export_submission:
        n_signals, n_evidence = despliegue.export_submission(result)
        print(f"\nEscrito {RESULTS_DIR}/signals.csv ({n_signals} filas) y {RESULTS_DIR}/evidence.csv ({n_evidence} filas)")


if __name__ == "__main__":
    main()
