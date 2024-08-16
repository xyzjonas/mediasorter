import os
import random
import shutil
from tempfile import TemporaryDirectory

import pytest

from mediasorter.lib.config import OperationOptions
from mediasorter.lib.sort import OperationHandler, Operation


@pytest.fixture
def tmp_tv_show(shows, shows_dir):
    show = os.path.join(shows_dir, random.choice(shows))
    with TemporaryDirectory() as tmp_src_dir:
        src_result = os.path.join(tmp_src_dir, os.path.basename(show))
        shutil.copy(show, src_result)
        assert os.path.exists(src_result)

        with TemporaryDirectory() as tmp_dest_dir:
            assert os.path.exists(tmp_dest_dir)
            yield src_result, os.path.join(tmp_dest_dir, os.path.basename(show))


@pytest.skip
@pytest.mark.asyncio
async def test_chown(tmp_tv_show):
    src, dest = tmp_tv_show

    opts = OperationOptions(chown=True, user=1001, group=1001)
    o = Operation(
        input_path=src,
        output_path=dest,
        action="copy",
        type="auto",
        options=opts,
    )
    handler = OperationHandler(o)
    await handler.commit()
