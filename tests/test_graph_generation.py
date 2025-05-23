import json
import unittest
from types import SimpleNamespace
from typing import Any, Dict, List

from pargraph import GraphEngine, delayed, graph
from pargraph.graph.objects import FunctionCall, Graph

try:
    import pandas as pd  # noqa

    PANDAS_INSTALLED = True
except ImportError:
    PANDAS_INSTALLED = False


class TestGraphGeneration(unittest.TestCase):
    engine: GraphEngine

    @classmethod
    def setUpClass(cls):
        cls.engine = GraphEngine()

    def test_basic(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(add(w, x), add(y, z))

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph().to_dict(w=1, x=2, y=3, z=4))[0], sample_graph(w=1, x=2, y=3, z=4)
        )

    def test_task_graph_positional_arguments(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(add(w, x), add(y, z))

        self.assertEqual(self.engine.get(*sample_graph.to_graph().to_dict(1, 2, 3, 4))[0], sample_graph(1, 2, 3, 4))

    def test_task_graph_positional_and_keyword_arguments(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(add(w, x), add(y, z))

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph().to_dict(1, 2, y=3, z=4))[0], sample_graph(1, 2, y=3, z=4)
        )

    def test_subgraph(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_subgraph(x: int, y: int) -> int:
            return add(x, y)

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return sample_subgraph(sample_subgraph(w, x), sample_subgraph(y, z))

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph().to_dict(w=1, x=2, y=3, z=4))[0], sample_graph(w=1, x=2, y=3, z=4)
        )

    def test_basic_partial(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(add(w, x), add(y, z))

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph(w=1, x=2).to_dict(y=3, z=4))[0], sample_graph(w=1, x=2, y=3, z=4)
        )

    def test_variadic_arguments(self):
        @delayed
        def add(*args: int) -> int:
            return sum(args)

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(w, x, y, z)

        self.assertEqual(self.engine.get(*sample_graph.to_graph().to_dict(w=1, x=2, y=3, z=4))[0], add(1, 2, 3, 4))

    def test_operator_override(self):
        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return (w + x) + (y + z)

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph().to_dict(w=1, x=2, y=3, z=4))[0], sample_graph(w=1, x=2, y=3, z=4)
        )

    def test_operator_override_complex(self):
        @graph
        def fibonacci(n: int) -> int:
            phi = (1 + 5**0.5) / 2
            return round(((phi**n) + ((1 - phi) ** n)) / 5**0.5)

        self.assertEqual(self.engine.get(*fibonacci.to_graph().to_dict(n=6))[0], fibonacci(n=6))

    def test_getitem(self):
        @delayed
        def return_tuple(x: int, y: int) -> Any:
            return x, y

        @graph
        def sample_graph(x: int, y: int) -> int:
            return return_tuple(x, y)[0]

        self.assertEqual(self.engine.get(*sample_graph.to_graph().to_dict(x=1, y=2))[0], sample_graph(x=1, y=2))

    @unittest.skipIf(not PANDAS_INSTALLED, "pandas must be installed")
    def test_call(self):
        import pandas as pd  # noqa

        @graph
        def sample_graph(s: pd.Series) -> int:
            return s.sum()

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph().to_dict(s=pd.Series([1, 2, 3])))[0],
            sample_graph(s=pd.Series([1, 2, 3])),
        )

    @unittest.skipIf(not PANDAS_INSTALLED, "pandas must be installed")
    def test_call_complex(self):
        import pandas as pd  # noqa

        @graph
        def sample_graph(s: pd.Series) -> pd.Series:
            return s[s > s.mean()]

        pd.testing.assert_series_equal(
            self.engine.get(*sample_graph.to_graph().to_dict(s=pd.Series([1, 2, 3])))[0],
            sample_graph(s=pd.Series([1, 2, 3])),
        )

    @unittest.skipIf(not PANDAS_INSTALLED, "pandas must be installed")
    def test_call_kw(self):
        import pandas as pd  # noqa

        @graph
        def sample_graph(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
            return df1.merge(df2, how="inner", on="a")

        pd.testing.assert_frame_equal(
            self.engine.get(
                *sample_graph.to_graph().to_dict(
                    df1=pd.DataFrame({"a": ["foo", "bar"], "b": [1, 2]}),
                    df2=pd.DataFrame({"a": ["foo", "baz"], "c": [3, 4]}),
                )
            )[0],
            sample_graph(
                df1=pd.DataFrame({"a": ["foo", "bar"], "b": [1, 2]}),
                df2=pd.DataFrame({"a": ["foo", "baz"], "c": [3, 4]}),
            ),
        )

    def test_boolean(self):
        @delayed
        def is_even(value: int) -> bool:
            return value % 2 == 0

        @delayed
        def is_positive(value: int) -> bool:
            return value >= 0

        @graph
        def invalid_graph(value: int) -> bool:
            return is_even(value) or is_positive(value)

        self.assertRaises(TypeError, invalid_graph.to_graph)

    def test_explode_subgraphs(self):
        @graph
        def sample_subgraph(x: int, y: int) -> int:
            return (x + y) * 2

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return sample_subgraph(sample_subgraph(w, x), sample_subgraph(y, z))

        self.assertGreater(
            len(sample_graph.to_graph().explode_subgraphs().nodes), len(sample_subgraph.to_graph().nodes)
        )

        self.assertEqual(
            self.engine.get(*sample_graph.to_graph().explode_subgraphs().to_dict(w=1, x=2, y=3, z=4))[0],
            sample_graph(w=1, x=2, y=3, z=4),
        )

    def test_stabilize(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(add(w, x), add(y, z))

        self.assertNotEqual(
            json.dumps(sample_graph.to_graph().to_json()), json.dumps(sample_graph.to_graph().to_json())
        )

        self.assertEqual(
            json.dumps(sample_graph.to_graph().stabilize().to_json()),
            json.dumps(sample_graph.to_graph().stabilize().to_json()),
        )

    def test_cull(self):
        @delayed
        def add(x: int, y: int) -> int:
            return x + y

        @graph
        def sample_graph(w: int, x: int, y: int, z: int) -> int:
            return add(add(w, x), add(y, z))

        generated_graph = sample_graph.to_graph()
        generated_graph = Graph(
            consts=generated_graph.consts, inputs=generated_graph.inputs, nodes=generated_graph.nodes, outputs={}
        )

        self.assertEqual(len(generated_graph.cull().nodes), 0)

    def test_fuse_sequential(self):
        @graph
        def attr_access(a: SimpleNamespace) -> int:
            return a.b.c.d.e

        self.assertEqual(
            self.engine.get(
                *attr_access.to_graph()
                .fuse_sequential()
                .to_dict(a=SimpleNamespace(b=SimpleNamespace(c=SimpleNamespace(d=SimpleNamespace(e=1)))))
            )[0],
            attr_access(a=SimpleNamespace(b=SimpleNamespace(c=SimpleNamespace(d=SimpleNamespace(e=1))))),
        )

        self.assertLess(len(attr_access.to_graph().fuse_sequential().nodes), len(attr_access.to_graph().nodes))

    def test_valid_delayed_signature(self):
        @delayed
        def valid1(arg: int) -> int: ...

        valid1(1)

        @delayed
        def valid2(arg1: int, arg2: int) -> int: ...

        valid2(1, 1)

        @delayed
        def valid3(*args: List[int]) -> int: ...

        valid3(1, 1, 1)

    def test_invalid_delayed_signature(self):
        with self.assertRaises(ValueError):

            @delayed
            def invalid1(**kwargs: Dict[str, int]) -> int: ...

            invalid1(a=1)

        with self.assertRaises(ValueError):

            @delayed
            def invalid2(arg: int, *args: List[int]) -> int: ...

            invalid2(1, 1)

        with self.assertRaises(ValueError):

            @delayed
            def invalid3(*args: List[int], **kwargs: Dict[str, int]) -> int: ...

            invalid3(1, 1, a=1)

    def test_valid_graph_signature(self):
        @graph
        def valid1(arg: int) -> int: ...

        valid1(1)

        @graph
        def valid2(arg1: int, arg2: int) -> int: ...

        valid2(1, 1)

    def test_invalid_graph_signature(self):
        with self.assertRaises(ValueError):

            @graph
            def invalid1(**kwargs: Dict[str, int]) -> int: ...

            invalid1(a=1)

        with self.assertRaises(ValueError):

            @graph
            def invalid2(*args: List[int]) -> int: ...

            invalid2(1, 1)

        with self.assertRaises(ValueError):

            @graph
            def invalid3(*args: List[int], **kwargs: Dict[str, int]) -> int: ...

            invalid3(1, 1, a=1)

    def test_implicit_tag(self):
        @graph
        def sample_graph(x: int, y: int) -> int:
            return x + y

        function_call = next(iter(sample_graph.to_graph().nodes.values()))

        assert isinstance(function_call, FunctionCall)
        self.assertEqual(getattr(function_call.function, "__implicit", False), True)

    def test_graph_default_argument(self):
        @graph
        def sample_graph(x: int, y: int = 1) -> int:
            return x + y

        self.assertEqual(self.engine.get(*sample_graph.to_graph().to_dict(x=2, y=3))[0], sample_graph(x=2, y=3))

    def test_graph_default_argument_missing(self):
        @graph
        def sample_graph(x: int, y: int = 1) -> int:
            return x + y

        self.assertEqual(self.engine.get(*sample_graph.to_graph().to_dict(x=2))[0], sample_graph(x=2))

    def test_function_default_argument(self):
        @graph
        def add(x: int, y: int = 1) -> int:
            return x + y

        self.assertEqual(self.engine.get(*add.to_graph().to_dict(x=2, y=3))[0], add(x=2, y=3))

    def test_function_default_argument_missing(self):
        @graph
        def add(x: int, y: int = 1) -> int:
            return x + y

        self.assertEqual(self.engine.get(*add.to_graph().to_dict(x=2))[0], add(x=2))

    def test_missing_input(self):
        @graph
        def add(x: int, y: int) -> int:
            return x + y

        with self.assertRaises(ValueError):
            add.to_graph().to_dict(x=2)
