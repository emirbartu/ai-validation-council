from council.models.report import AnalysisReport, CouncilAddendum, DebateSummary, SWOTAnalysis


class TestDebateSummary:
    def test_empty_lists_valid(self):
        ds = DebateSummary()
        assert ds.what_agents_agreed_on == []
        assert ds.what_would_strengthen_the_idea == []
        assert ds.key_disadvantages == []

    def test_populated_lists(self):
        ds = DebateSummary(
            what_agents_agreed_on=["Market is growing"],
            what_would_strengthen_the_idea=["Find distribution partner"],
            key_disadvantages=["High CAC"],
        )
        assert len(ds.what_agents_agreed_on) == 1


class TestSWOTAnalysis:
    def test_empty_valid(self):
        swot = SWOTAnalysis()
        assert swot.strengths == []

    def test_minimum_two_items(self):
        try:
            SWOTAnalysis(strengths=["Only one"], weaknesses=[], opportunities=[], threats=[])
            raise AssertionError("Should have raised ValueError")
        except Exception:
            pass

    def test_maximum_five(self):
        try:
            SWOTAnalysis(
                strengths=["s1", "s2", "s3", "s4", "s5", "s6"],
                weaknesses=[],
                opportunities=[],
                threats=[],
            )
            raise AssertionError("Should have raised ValueError")
        except Exception:
            pass

    def test_two_to_five_valid(self):
        swot = SWOTAnalysis(
            strengths=["s1", "s2"],
            weaknesses=["w1", "w2"],
            opportunities=["o1", "o2"],
            threats=["t1", "t2"],
        )
        assert len(swot.strengths) == 2


class TestCouncilAddendum:
    def test_default_null(self):
        report = AnalysisReport(query="test")
        assert report.addendum is None

    def test_populated(self):
        a = CouncilAddendum(
            topic="Hidden risk", insight="Something new", raised_by="devils_advocate"
        )
        assert a.raised_by == "devils_advocate"
