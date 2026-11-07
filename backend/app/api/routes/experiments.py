from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import build_experiment_service, get_api_key
from app.schemas.experiment import ExperimentCreate
from app.services.evaluation import describe_all

router = APIRouter(prefix="/api", tags=["experiments"])


@router.get("/evaluators")
def list_evaluators():
    return describe_all()


# Plain `def` routes run in the threadpool; an experiment makes many blocking model calls.
@router.post("/experiments", status_code=status.HTTP_201_CREATED)
def run_experiment(body: ExperimentCreate, request: Request,
                   api_key: str | None = Depends(get_api_key)):
    return build_experiment_service(request, api_key).run(body)


@router.get("/experiments")
def list_experiments(request: Request, project_id: str | None = Query(None, max_length=64),
                     skip: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    return build_experiment_service(request, None).list(project_id, skip, limit)


@router.get("/experiments/compare")
def compare_experiments(request: Request, ids: str = Query(..., max_length=300)):
    return build_experiment_service(request, None).compare(
        [i.strip() for i in ids.split(",") if i.strip()]
    )


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, request: Request):
    return build_experiment_service(request, None).get(experiment_id)


@router.get("/experiments/{experiment_id}/results")
def experiment_results(experiment_id: str, request: Request, skip: int = Query(0, ge=0),
                       limit: int = Query(50, ge=1, le=200)):
    return build_experiment_service(request, None).results(experiment_id, skip, limit)
