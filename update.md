# Plan de correction et d'amélioration — Petalia Geospatial Engine

> Basé sur l'audit géomatique / télédétection / architecture du 2026-05-18.
> Chaque item précise : problème → fichier(s) → changement exact → impact attendu.

---

## SPRINT 1 — Correctifs scientifiques critiques

> Ne pas déployer en production sans ces corrections. Les résultats actuels sont
> scientifiquement incorrects ou peuvent provoquer des erreurs runtime.

---

### S1-1 · SCL masking incomplet (classes 0 et 1 manquantes)

**Problème**
Le masque SCL actuel exclut `[3, 8, 9, 10]` mais oublie :
- Classe 0 (No Data) → pixels invalides qui faussent tous les indices
- Classe 1 (Saturated/Defective) → pixels radiométriquement défectueux

**Fichier** : `src/infrastructure/earth_engine/image_fetcher.py`

**Changement**
```python
# AVANT
cloud_mask = (
    scl.neq(3)
    .And(scl.neq(8))
    .And(scl.neq(9))
    .And(scl.neq(10))
)

# APRÈS — approche conservatrice agriculture (standard 2024)
cloud_mask = (
    scl.neq(0)   # No Data
    .And(scl.neq(1))   # Saturated / Defective
    .And(scl.neq(3))   # Cloud Shadow
    .And(scl.neq(8))   # Cloud Medium Probability
    .And(scl.neq(9))   # Cloud High Probability
    .And(scl.neq(10))  # Thin Cirrus
)
```

**Impact** : Suppression des pixels invalides qui biaisaient NDVI/NDMI.
**Test** : Vérifier que les valeurs NDVI sur une parcelle saine restent dans [0.3, 0.9].

---

### S1-2 · Trend calculé sur une seule image (invalide scientifiquement)

**Problème**
`_compute_trend(ndvi_mean, ndvi_std)` dérive une "tendance temporelle" à partir
d'une unique image. Une tendance nécessite au minimum deux observations dans le
temps. Ce qui est calculé actuellement est une classification ponctuelle, pas une
tendance. La logique est aussi incohérente : NDVI 0.5 → `UP` même si la semaine
dernière il était à 0.8.

**Fichiers**
- `src/infrastructure/earth_engine/index_calculator.py` → supprimer `_compute_trend`, retourner `None`
- `src/domain/entities/vegetation_metrics.py` → supprimer le champ `trend` de `create()`
- `src/domain/services/alert_detection_service.py` → calculer la tendance réelle
- `src/infrastructure/workers/analysis_worker.py` → passer `previous_metrics` au calcul

**Changement dans `index_calculator.py`**
```python
# Supprimer _compute_trend()
# IndexResult : supprimer le champ trend
@dataclass
class IndexResult:
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndwi_mean: float
    variability_index: float
    # trend retiré — calculé plus tard avec previous_metrics
```

**Nouveau calcul de tendance dans `alert_detection_service.py`**
```python
@staticmethod
def _compute_trend(
    current: VegetationMetrics,
    previous: VegetationMetrics | None,
) -> VegetationTrend:
    if previous is None:
        return VegetationTrend.STABLE  # pas assez de données
    delta = current.ndvi_mean - previous.ndvi_mean
    if delta > 0.05:
        return VegetationTrend.UP
    if delta < -0.05:
        return VegetationTrend.DOWN
    return VegetationTrend.STABLE
```

**Dans `analysis_worker.py`** : passer `previous_metrics` à `VegetationMetrics.create()`.

**Impact** : Trend correct, basé sur l'évolution réelle dans le temps.
**Test** : Deux analyses successives sur le même champ → trend cohérent.

---

### S1-3 · NDWI mal nommé → renommer en NDMI

**Problème**
`(B8 - B11) / (B8 + B11)` est le **NDMI** (Gao 1996, stress hydrique foliaire),
pas le **NDWI** (McFeeters 1996, détection eau libre). Le nom trompeur dans l'API
induira les utilisateurs en erreur.

**Fichiers**
- `src/infrastructure/earth_engine/index_calculator.py`
- `src/domain/entities/vegetation_metrics.py`
- `src/infrastructure/database/models.py`
- `src/presentation/schemas/` (champs `ndwiMean` → `ndmiMean`)
- `src/application/dto/analysis_dto.py`
- `alembic/versions/` → nouvelle migration de renommage de colonne

**Changement clé dans `index_calculator.py`**
```python
# AVANT
ndwi = image.normalizedDifference(["B8", "B11"]).rename("NDWI")
ndwi_stats = ndwi.reduceRegion(reducer=ee.Reducer.mean(), ...)
ndwi_mean = float(ndwi_stats.get("NDWI") or 0.0)

# APRÈS
ndmi = image.normalizedDifference(["B8", "B11"]).rename("NDMI")
ndmi_stats = ndmi.reduceRegion(reducer=ee.Reducer.mean(), ...)
ndmi_mean = float(ndmi_stats.get("NDMI") or 0.0)
```

**Migration Alembic** : `002_rename_ndwi_to_ndmi.py`
```python
op.alter_column("vegetation_metrics", "ndwi_mean", new_column_name="ndmi_mean")
```

**Impact** : Terminologie correcte, API lisible par un géomaticien.

---

### S1-4 · Acquisition date sans timezone

**Problème**
`datetime.strptime(latest_date_info, "%Y-%m-%d")` retourne un datetime
timezone-naive. Le champ PostGIS `DateTime(timezone=True)` et `utcnow()` sont
timezone-aware → comparaisons provoquent `TypeError` en Python 3.11+.

**Fichier** : `src/infrastructure/earth_engine/image_fetcher.py`

**Changement**
```python
from datetime import UTC

# AVANT
acquisition_date = datetime.strptime(latest_date_info, "%Y-%m-%d")

# APRÈS
acquisition_date = datetime.strptime(latest_date_info, "%Y-%m-%d").replace(tzinfo=UTC)
```

**Impact** : Suppression d'une source de `TypeError` en production.

---

## SPRINT 2 — Valeur métier et richesse des données

> Améliore directement la qualité agronomique du service.

---

### S2-1 · Ajout NDRE, SAVI, EVI2

**Problème**
NDVI + NDMI seulement. Manquent des indices critiques pour l'agriculture de
précision :
- **NDRE** (Red-Edge) : stress azoté, chlorophylle — détecte le stress 2-3 semaines
  avant que le NDVI ne le voit
- **SAVI** : corrige l'effet du sol nu (stades juvéniles, cultures éparses)
- **EVI2** : corrige la saturation du NDVI sur cultures denses (maïs, tournesol)

**Fichier** : `src/infrastructure/earth_engine/index_calculator.py`

**Changement dans `IndexResult`**
```python
@dataclass
class IndexResult:
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndmi_mean: float      # ex-NDWI
    ndre_mean: float      # NOUVEAU
    savi_mean: float      # NOUVEAU
    evi2_mean: float      # NOUVEAU
    variability_index: float
```

**Calcul dans `compute()`**
```python
# NDRE — bandes 20m, sensible au chlorophylle
ndre = image.normalizedDifference(["B8A", "B5"]).rename("NDRE")

# SAVI — L=0.5 standard, bandes 10m
savi = image.expression(
    "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
    {"NIR": image.select("B8"), "RED": image.select("B4")}
).rename("SAVI")

# EVI2 — sans bande bleue, plus robuste au bruit atmosphérique
evi2 = image.expression(
    "2.5 * (NIR - RED) / (NIR + 2.4 * RED + 1)",
    {"NIR": image.select("B8"), "RED": image.select("B4")}
).rename("EVI2")

# Reducer combiné pour un seul passage GEE
multi_reducer = ee.Reducer.mean()
indices_stats = (
    ndvi.addBands(ndmi).addBands(ndre).addBands(savi).addBands(evi2)
    .reduceRegion(
        reducer=multi_reducer,
        geometry=ee_geometry,
        scale=20,
        maxPixels=1e9,
        bestEffort=False,
    ).getInfo()
)
```

**Migration** : `003_add_ndre_savi_evi2.py` — nouvelles colonnes dans `vegetation_metrics`.

**Impact** : Détection précoce du stress azoté, meilleure précision sur cultures juvéniles.

---

### S2-2 · Nouvelles alertes agronomiques

**Problème**
Seuls 3 types d'alertes : `NDVI_LOW`, `NDVI_DROP`, `HIGH_CLOUD_COVER`.
Manquent des alertes directement actionnables par l'agriculteur.

**Fichier** : `src/domain/value_objects/alert_type.py`
```python
class AlertType(StrEnum):
    NDVI_LOW = "NDVI_LOW"
    NDVI_DROP = "NDVI_DROP"
    HIGH_CLOUD_COVER = "HIGH_CLOUD_COVER"
    WATER_STRESS = "WATER_STRESS"       # NOUVEAU — NDMI < seuil
    NITROGEN_STRESS = "NITROGEN_STRESS" # NOUVEAU — NDRE < seuil
    HIGH_VARIABILITY = "HIGH_VARIABILITY" # NOUVEAU — hétérogénéité intra-parcelle
```

**Fichier** : `src/domain/services/alert_detection_service.py`

**Nouveaux checks**
```python
def _check_water_stress(self, field_id, analysis_id, metrics) -> list[AgronomicAlert]:
    # NDMI < -0.1 : stress hydrique significatif
    if metrics.ndmi_mean > -0.1:
        return []
    severity = (
        AlertSeverity.CRITICAL if metrics.ndmi_mean < -0.3
        else AlertSeverity.HIGH if metrics.ndmi_mean < -0.2
        else AlertSeverity.MEDIUM
    )
    return [AgronomicAlert.create(
        field_id=field_id,
        analysis_id=analysis_id,
        severity=severity,
        alert_type=AlertType.WATER_STRESS,
        message=f"Stress hydrique détecté (NDMI={metrics.ndmi_mean:.2f}). "
                "Irrigation recommandée.",
    )]

def _check_nitrogen_stress(self, field_id, analysis_id, metrics) -> list[AgronomicAlert]:
    # NDRE < 0.2 : déficience azotée possible
    if metrics.ndre_mean > 0.2:
        return []
    return [AgronomicAlert.create(
        field_id=field_id,
        analysis_id=analysis_id,
        severity=AlertSeverity.MEDIUM,
        alert_type=AlertType.NITROGEN_STRESS,
        message=f"Possible déficience azotée (NDRE={metrics.ndre_mean:.2f}). "
                "Analyse foliaire recommandée.",
    )]

def _check_high_variability(self, field_id, analysis_id, metrics) -> list[AgronomicAlert]:
    # variability_index > 0.3 : hétérogénéité intra-parcelle élevée
    if metrics.variability_index <= 0.3:
        return []
    return [AgronomicAlert.create(
        field_id=field_id,
        analysis_id=analysis_id,
        severity=AlertSeverity.LOW,
        alert_type=AlertType.HIGH_VARIABILITY,
        message=f"Forte hétérogénéité intra-parcelle (VI={metrics.variability_index:.2f}). "
                "Zones à problème potentielles.",
    )]
```

**Nouveaux settings dans `settings.py`**
```python
ndmi_stress_threshold: float = -0.10
ndre_low_threshold: float = 0.20
variability_high_threshold: float = 0.30
```

**Impact** : Alertes actionnables pour irrigation, fertilisation, modulation intra-parcellaire.

---

### S2-3 · TTL Redis tiles ≤ 48h

**Problème**
Les URLs `getMapId()` / `getThumbURL()` GEE expirent après 1-7 jours.
`REDIS_CACHE_TTL_TILES=2592000` (30 jours) → URLs mortes servies aux clients.

**Fichier** : `src/shared/config/settings.py`
```python
# AVANT
redis_cache_ttl_tiles: int = 2592000   # 30 jours

# APRÈS
redis_cache_ttl_tiles: int = 172800    # 48h — aligné sur expiration GEE
```

**Alternative plus robuste** : régénérer les tiles à la demande si Redis miss
(endpoint `/tiles` appelle GEE directement si cache vide, et re-stocke 48h).
Implémenter dans `get_field_tiles` endpoint.

**Impact** : Suppression des URLs expirées retournées aux clients.

---

### S2-4 · Peupler le champ `geom` PostGIS

**Problème**
PostGIS est activé mais la colonne `geom` n'est jamais écrite. Les capacités
d'analyse spatiale (intersection de parcelles, zones tampons, requêtes par
bounding box) sont bloquées.

**Fichier** : `src/infrastructure/database/repositories/field_repository_impl.py`

**Changement dans `save()` et `update()`**
```python
# Lors de la persistance du champ
model.geom = f"SRID=4326;{shape(field.geometry.geojson).wkt}"
```

**Migration** : `004_geom_column_geometry_type.py`
```python
# Changer le type Text en Geometry PostGIS
op.execute("""
    ALTER TABLE fields
    ALTER COLUMN geom TYPE geometry(Geometry, 4326)
    USING ST_GeomFromText(geom, 4326)
""")
op.execute("""
    CREATE INDEX ix_fields_geom ON fields USING GIST (geom)
""")
```

**Impact** : Débloque les requêtes spatiales PostGIS pour les futures features.

---

### S2-5 · Brancher les métriques Prometheus

**Problème**
`src/infrastructure/monitoring/metrics.py` définit des counters/histograms
mais ne sont jamais incrémentés → dashboard Grafana vide.

**Fichier** : `src/infrastructure/workers/analysis_worker.py`

**Changement**
```python
from src.infrastructure.monitoring.metrics import (
    analyses_created_total,
    analysis_duration_seconds,
    gee_requests_total,
    alerts_generated_total,
)

# Dans _execute_pipeline() — au début
start_time = time.monotonic()

# Après mark_completed()
duration = time.monotonic() - start_time
analysis_duration_seconds.observe(duration)
analyses_created_total.labels(status="completed").inc()
alerts_generated_total.labels(field_id=field_id).inc(len(alerts_list))

# Dans le bloc except
analyses_created_total.labels(status="failed").inc()
```

**Fichier** : `src/infrastructure/earth_engine/image_fetcher.py`
```python
gee_requests_total.labels(operation="fetch").inc()
```

**Impact** : Dashboard Grafana opérationnel, alerting Prometheus possible.

---

## SPRINT 3 — Robustesse et performance GEE

---

### S3-1 · Fenêtre temporelle adaptative

**Problème**
`SENTINEL_DATE_RANGE_DAYS=30` statique. En cas de forte couverture nuageuse
(automne/hiver, zones côtières), 30 jours donnent 0 image propre. Le fallback
actuel supprime le filtre cloud mais ne recule pas dans le temps.

**Fichier** : `src/infrastructure/earth_engine/image_fetcher.py`

**Nouveau comportement**
```python
def fetch(self, geometry: dict[str, Any]) -> ImageFetchResult:
    for days in [30, 60, 90]:  # Fenêtre adaptative
        start_date, end_date = date_range_strings(days)
        collection = self._build_collection(geometry, start_date, end_date, with_cloud_filter=True)
        count = collection.size().getInfo()
        if count > 0:
            logger.info("sentinel_window_used", days=days, count=count)
            break
    else:
        # Dernier recours : sans filtre cloud, 90 jours
        collection = self._build_collection(geometry, start_date, end_date, with_cloud_filter=False)
        count = collection.size().getInfo()
        if count == 0:
            raise EarthEngineException("Aucune image Sentinel-2 disponible pour cette zone.")

    return self._build_result(collection, geometry)

def _build_collection(self, geometry, start_date, end_date, with_cloud_filter):
    col = (
        ee.ImageCollection(self._settings.sentinel_dataset)
        .filterBounds(ee.Geometry(geometry))
        .filterDate(start_date, end_date)
        .map(self._apply_scl_mask)
    )
    if with_cloud_filter:
        col = col.filter(
            ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self._settings.sentinel_cloud_max)
        )
    return col
```

**Nouveau setting** : `SENTINEL_DATE_RANGE_MAX_DAYS=90`

**Impact** : Résilience en zones à fort couvert nuageux, 0 analyse bloquée sur collection vide.

---

### S3-2 · bestEffort=False + scale explicite

**Problème**
`bestEffort=True` permet à GEE d'augmenter silencieusement la résolution
d'analyse. Sur des parcelles agricoles de 2-10 ha, cela peut passer de 20m à
500m, rendant les statistiques inutilisables.

**Fichier** : `src/infrastructure/earth_engine/index_calculator.py`

**Changement**
```python
# AVANT
bestEffort=True,

# APRÈS — échelle 20m pour cohérence avec les bandes SWIR (B11, B12)
bestEffort=False,
scale=20,
maxPixels=1e9,
```

**Note** : Pour les très grandes parcelles (> 10 000 ha), prévoir un export
`ee.batch` au lieu d'un appel interactif (voir S3-4).

---

### S3-3 · Timeout sur les appels GEE `.getInfo()`

**Problème**
`.getInfo()` peut bloquer indéfiniment si GEE est lent ou surchargé.
Aucun timeout configuré → Celery task bloquée.

**Fichier** : `src/infrastructure/earth_engine/index_calculator.py`

**Changement**
```python
import concurrent.futures

GEE_TIMEOUT_SECONDS = 120

def _getinfo_with_timeout(ee_object, timeout: int = GEE_TIMEOUT_SECONDS):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(ee_object.getInfo)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise EarthEngineException(
                f"GEE ne répond pas après {timeout}s. Réessayez plus tard."
            )
```

**Impact** : Celery tasks terminées proprement en cas de timeout GEE.

---

### S3-4 · Validation taille de parcelle

**Problème**
Aucune limite sur `area_ha`. Une parcelle de 500 000 ha en interactif timeout GEE
sans message utile.

**Fichier** : `src/application/use_cases/create_analysis_use_case.py`

**Changement**
```python
# Dans execute()
MAX_AREA_HA = get_settings().max_field_area_ha  # nouveau setting, default=50000

area_ha = compute_area_hectares(command.geometry)
if area_ha > MAX_AREA_HA:
    raise InvalidGeometryException(
        f"Surface ({area_ha:.0f} ha) dépasse le maximum autorisé ({MAX_AREA_HA} ha). "
        "Découpez la zone en sous-parcelles."
    )
```

**Nouveau setting** : `MAX_FIELD_AREA_HA=50000`

---

### S3-5 · CASCADE DELETE sur les Foreign Keys

**Problème**
Supprimer un `field` laisse des orphelins dans `analyses`, `vegetation_metrics`,
`agronomic_alerts`.

**Migration** : `005_add_cascade_delete.py`
```python
def upgrade():
    # Supprimer les FK existantes et les recréer avec CASCADE
    op.drop_constraint("analyses_field_id_fkey", "analyses", type_="foreignkey")
    op.create_foreign_key(
        "analyses_field_id_fkey", "analyses", "fields",
        ["field_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("agronomic_alerts_field_id_fkey", "agronomic_alerts", type_="foreignkey")
    op.create_foreign_key(
        "agronomic_alerts_field_id_fkey", "agronomic_alerts", "fields",
        ["field_id"], ["id"], ondelete="CASCADE"
    )
    # analyses → satellite_observations, vegetation_metrics, agronomic_alerts
    for table in ["satellite_observations", "vegetation_metrics", "agronomic_alerts"]:
        op.drop_constraint(f"{table}_analysis_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_analysis_id_fkey", table, "analyses",
            ["analysis_id"], ["id"], ondelete="CASCADE"
        )
```

---

### S3-6 · Composite percentile(40) en alternative au median

**Problème**
`median()` sur des collections courtes (3-5 scènes) peut inclure des pixels
nuageux résiduels. Études 2024 montrent que le percentile 40 produit moins
d'artefacts avec le même temps de calcul.

**Fichier** : `src/infrastructure/earth_engine/image_fetcher.py`

**Changement + nouveau setting**
```python
# Nouveau setting
composite_method: str = "median"  # "median" | "p40" | "p80" | "quality_mosaic"

# Dans _build_result()
if self._settings.composite_method == "p40":
    composite = collection.reduce(ee.Reducer.percentile([40])).clip(ee_geometry)
elif self._settings.composite_method == "p80":
    composite = collection.reduce(ee.Reducer.percentile([80])).clip(ee_geometry)
elif self._settings.composite_method == "quality_mosaic":
    def add_ndvi(img):
        return img.addBands(img.normalizedDifference(["B8", "B4"]).rename("NDVI"))
    composite = collection.map(add_ndvi).qualityMosaic("NDVI").clip(ee_geometry)
else:
    composite = collection.median().clip(ee_geometry)
```

---

## SPRINT 4 — Features avancées

> Features à planifier selon la roadmap produit.

---

### S4-1 · API batch multi-parcelles

**Problème** : Un seul champ par requête. Agriculteurs avec 100+ parcelles
= 100+ requêtes.

**Nouvel endpoint** : `POST /v1/analyses/batch`

```python
class BatchAnalysisRequest(BaseModel):
    fields: list[CreateAnalysisRequest] = Field(..., max_length=50)

class BatchAnalysisResponse(BaseModel):
    submitted: int
    analyses: list[CreateAnalysisResponse]
    errors: list[dict]
```

**Celery** : Utiliser `group()` pour grouper les tasks + `chord()` pour
callback quand toutes sont terminées.

---

### S4-2 · Cloud Score+ en complément du SCL

**Problème** : SCL a été conçu pour la correction atmosphérique, pas pour la
détection de nuages fins. Cloud Score+ (Google, 2023) est supérieur pour les
nuages fins, cirrus, et les zones de transition.

**Fichier** : `src/infrastructure/earth_engine/image_fetcher.py`

```python
def _apply_cloud_score_plus_mask(image: Any) -> Any:
    """Masque hybride SCL + Cloud Score+ pour qualité maximale."""
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED") \
           .filterBounds(image.geometry()) \
           .filterDate(
               ee.Date(image.date().format()),
               ee.Date(image.date().advance(1, "day"))
           ).first()
    # Score > 0.6 = pixel propre (0=nuageux, 1=clair)
    cloud_score_mask = cs.select("cs").gte(0.6)
    return image.updateMask(cloud_score_mask)
```

Combiner avec le masque SCL existant pour une couverture maximale.

---

### S4-3 · Endpoint de séries temporelles multi-index

**Problème** : `/v1/fields/{field_id}/timeseries` retourne NDVI/NDWI seulement.
Avec les nouveaux indices (NDRE, SAVI, EVI2), l'endpoint doit être étendu.

**Nouveau schéma**
```python
class TimeseriesEntryResponse(BaseModel):
    analysisId: str          # noqa: N815
    analysisDate: datetime   # noqa: N815
    ndviMean: float          # noqa: N815
    ndmiMean: float          # noqa: N815 (ex-ndwiMean)
    ndreMean: float | None   # noqa: N815
    saviMean: float | None   # noqa: N815
    evi2Mean: float | None   # noqa: N815
    cloudCoverage: float | None  # noqa: N815
    trend: VegetationTrend
    health: VegetationHealth
```

---

### S4-4 · Export GEE batch pour grandes zones

**Problème** : Parcelles > 50 000 ha nécessitent `ee.batch.Export` au lieu
d'appels interactifs `.getInfo()`.

**Architecture** :
```
POST /v1/analyses  →  CreateAnalysisUseCase
    ├── si area_ha < MAX_INTERACTIVE_HA (5000) → run_analysis (Celery interactif)
    └── si area_ha >= MAX_INTERACTIVE_HA → run_analysis_batch (Celery + GEE Export)
```

**Task Celery batch** :
1. `ee.batch.Export.image.toDrive(...)` → déclenche l'export GEE
2. Polling toutes les 2min jusqu'à `COMPLETED`
3. Télécharge le GeoTIFF depuis Drive
4. Calcule les statistiques localement (rasterio/numpy)
5. Supprime le fichier Drive temporaire

---

### S4-5 · Contextualisation phénologique des seuils NDVI

**Problème** : Les seuils NDVI sont statiques (0.10/0.20/0.30). Un NDVI de 0.25
est normal en germination (mars) mais critique en pleine saison (juillet).

**Approche** :
```python
# settings.py — seuils par période
PHENOLOGY_THRESHOLDS = {
    "early_season": {"doy_range": (60, 150), "ndvi_low": 0.15},   # Mars-Mai
    "peak_season":  {"doy_range": (150, 240), "ndvi_low": 0.40},  # Juin-Août
    "late_season":  {"doy_range": (240, 330), "ndvi_low": 0.20},  # Sept-Nov
}
```

```python
# Dans AlertDetectionService
from datetime import date

def _get_seasonal_threshold(self) -> float:
    doy = date.today().timetuple().tm_yday
    for period, config in PHENOLOGY_THRESHOLDS.items():
        if config["doy_range"][0] <= doy <= config["doy_range"][1]:
            return config["ndvi_low"]
    return self._ndvi_low_threshold  # fallback
```

---

## Tableau récapitulatif

| # | Item | Sprint | Priorité | Effort | Impact |
|---|------|--------|----------|--------|--------|
| S1-1 | SCL mask classes 0 et 1 | 1 | 🔴 Bloquant | 30 min | Qualité données |
| S1-2 | Trend calculé correctement | 1 | 🔴 Bloquant | 3h | Scientifique |
| S1-3 | NDWI → NDMI (renommage) | 1 | 🔴 Bloquant | 2h | Terminologie |
| S1-4 | Acquisition date + timezone | 1 | 🔴 Bloquant | 15 min | Stabilité |
| S2-1 | Indices NDRE, SAVI, EVI2 | 2 | 🟠 Important | 1j | Valeur métier |
| S2-2 | Alertes WATER_STRESS, NITROGEN | 2 | 🟠 Important | 4h | Valeur métier |
| S2-3 | TTL tiles Redis 48h | 2 | 🟠 Important | 30 min | UX |
| S2-4 | Peupler geom PostGIS | 2 | 🟠 Important | 2h | Futur |
| S2-5 | Métriques Prometheus | 2 | 🟠 Important | 3h | Monitoring |
| S3-1 | Fenêtre temporelle adaptative | 3 | 🟡 Moyen | 2h | Résilience |
| S3-2 | bestEffort=False + scale=20 | 3 | 🟡 Moyen | 30 min | Précision |
| S3-3 | Timeout getInfo() GEE | 3 | 🟡 Moyen | 1h | Stabilité |
| S3-4 | Validation taille parcelle | 3 | 🟡 Moyen | 1h | Robustesse |
| S3-5 | CASCADE DELETE FK | 3 | 🟡 Moyen | 1h | Intégrité données |
| S3-6 | Composite percentile(40) | 3 | 🟢 Optionnel | 1h | Qualité |
| S4-1 | API batch multi-parcelles | 4 | 🟢 Feature | 2j | Scale |
| S4-2 | Cloud Score+ masking | 4 | 🟢 Feature | 4h | Qualité données |
| S4-3 | Timeseries multi-index | 4 | 🟢 Feature | 4h | UX |
| S4-4 | Export GEE batch grandes zones | 4 | 🟢 Feature | 3j | Scale |
| S4-5 | Seuils phénologiques | 4 | 🟢 Feature | 1j | Agronomie |

---

## Migrations Alembic à créer

```
alembic/versions/
├── 001_initial_schema.py          ✅ existant
├── 002_rename_ndwi_to_ndmi.py     📝 Sprint 1
├── 003_add_ndre_savi_evi2.py      📝 Sprint 2
├── 004_geom_column_geometry_type.py 📝 Sprint 2
└── 005_add_cascade_delete.py      📝 Sprint 3
```

## Tests à ajouter / mettre à jour

| Fichier | Ce qu'il teste |
|---------|---------------|
| `tests/unit/domain/test_alert_detection_service.py` | Nouvelles alertes WATER_STRESS, NITROGEN |
| `tests/unit/earth_engine/test_scl_mask.py` | Classes 0 et 1 effectivement masquées |
| `tests/unit/earth_engine/test_trend_computation.py` | Trend calculé sur 2 observations |
| `tests/unit/earth_engine/test_index_calculator.py` | NDRE, SAVI, EVI2 présents dans IndexResult |
| `tests/unit/domain/test_vegetation_metrics.py` | Champs ndmi_mean, ndre_mean présents |
| `tests/api/test_analyses_endpoints.py` | Réponse contient ndmiMean (pas ndwiMean) |
| `tests/api/test_fields_endpoints.py` | TTL tiles ≤ 172800 |
