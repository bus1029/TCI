from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tci.domain.services.build_code_snapshot import (  # noqa: E402
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (  # noqa: E402
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tests.support.repository_connection_testkit import (  # noqa: E402
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def main() -> None:
    # SC-001은 운영 화면/연결 생성 이후 첫 스냅샷 확인까지의 최소 기준선을 반복 측정할 수 있어야 한다.
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_id = uuid.uuid4()
        client, store = create_test_client(
            tmp_path=Path(tmp_dir),
            workspace_id=workspace_id,
        )
        seed_planning_input_reference(store, workspace_id=workspace_id)

        start = time.perf_counter()
        create_response = client.post(
            "/api/repository-connections",
            json=create_connection_payload(),
        )
        connection_id = uuid.UUID(create_response.json()["id"])
        sync_run = create_initial_snapshot(
            CreateInitialSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=client.app.state.dependencies,
        )
        snapshot = build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=client.app.state.dependencies,
        )
        client.get(
            f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
        )
        elapsed = time.perf_counter() - start

        print(f"SC001_SECONDS={elapsed:.4f}")
        print(f"CONNECTION_ID={connection_id}")
        print(f"SNAPSHOT_ID={snapshot.id}")


if __name__ == "__main__":
    main()
