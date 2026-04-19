# -*- coding: utf-8 -*-

from learn_tantivy import api


def test():
    _ = api


if __name__ == "__main__":
    from learn_tantivy.tests import run_cov_test

    run_cov_test(
        __file__,
        "learn_tantivy.api",
        preview=False,
    )
