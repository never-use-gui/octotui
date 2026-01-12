"""Tests for the graph layout lane assignment algorithm and multi-lane rendering."""

import pytest
import git
from octotui.graph_layout import GraphLayoutEngine
from octotui.commit_graph import GitGraphRenderer
from octotui.graph_data import CommitNode, CommitGraph, CommitType
from datetime import datetime


class TestLaneAssignment:
    """Test suite for lane assignment algorithm."""
    
    @pytest.fixture
    def repo(self):
        """Get the current git repository."""
        return git.Repo(".")
    
    @pytest.fixture
    def graph(self, repo):
        """Build a graph from the current repository."""
        engine = GraphLayoutEngine(repo)
        return engine.build_graph(max_commits=50)
    
    def test_graph_builds_successfully(self, graph):
        """Test that the graph builds without errors."""
        assert graph is not None
        assert len(graph.commits) > 0
    
    def test_all_commits_have_valid_lanes(self, graph):
        """Test that all commits have non-negative lane assignments."""
        for commit in graph.commits.values():
            assert commit.lane >= 0, f"Commit {commit.short_sha} has invalid lane {commit.lane}"
    
    def test_max_lanes_is_positive(self, graph):
        """Test that max_lanes is at least 1."""
        assert graph.max_lanes >= 1
    
    def test_lane_assignments_within_max(self, graph):
        """Test that no commit has a lane >= max_lanes."""
        for commit in graph.commits.values():
            assert commit.lane < graph.max_lanes, (
                f"Commit {commit.short_sha} has lane {commit.lane} >= max_lanes {graph.max_lanes}"
            )
    
    def test_active_lanes_populated(self, graph):
        """Test that active_lanes is populated for each commit."""
        commits = graph.get_commits_in_order()
        for commit in commits:
            # active_lanes should be a set (may be empty for initial commits)
            assert isinstance(commit.active_lanes, set)
    
    def test_color_index_assigned(self, graph):
        """Test that color_index is assigned based on lane."""
        for commit in graph.commits.values():
            expected_color = commit.lane % len(graph.colors)
            assert commit.color_index == expected_color, (
                f"Commit {commit.short_sha} has color_index {commit.color_index}, "
                f"expected {expected_color} for lane {commit.lane}"
            )
    
    def test_merge_commits_have_merge_source_lanes(self, graph):
        """Test that merge commits with multiple parents in graph have merge_source_lanes."""
        for commit in graph.commits.values():
            if commit.is_merge():
                # Count parents that are in our graph
                parents_in_graph = [
                    p for p in commit.parent_shas if graph.get_commit(p)
                ]
                if len(parents_in_graph) > 1:
                    # Should have merge_source_lanes or the lanes converged
                    # (merge_source_lanes may be empty if all parents have same lane)
                    assert isinstance(commit.merge_source_lanes, list)
    
    def test_edges_have_valid_lanes(self, graph):
        """Test that all edges have valid from_lane and to_lane."""
        for edge in graph.edges:
            assert edge.from_lane >= 0, f"Edge has invalid from_lane {edge.from_lane}"
            assert edge.to_lane >= 0, f"Edge has invalid to_lane {edge.to_lane}"


class TestGraphLayoutEngine:
    """Test suite for GraphLayoutEngine class."""
    
    @pytest.fixture
    def repo(self):
        """Get the current git repository."""
        return git.Repo(".")
    
    def test_engine_initialization(self, repo):
        """Test that engine initializes correctly."""
        engine = GraphLayoutEngine(repo)
        assert engine.repo == repo
        assert engine.graph is not None
    
    def test_build_graph_returns_commit_graph(self, repo):
        """Test that build_graph returns a CommitGraph."""
        engine = GraphLayoutEngine(repo)
        graph = engine.build_graph(max_commits=10)
        from octotui.graph_data import CommitGraph
        assert isinstance(graph, CommitGraph)
    
    def test_build_graph_respects_max_commits(self, repo):
        """Test that build_graph respects max_commits limit."""
        engine = GraphLayoutEngine(repo)
        graph = engine.build_graph(max_commits=5)
        assert len(graph.commits) <= 5
    
    def test_empty_repo_handling(self, tmp_path):
        """Test that engine handles empty repos gracefully."""
        # Create a new empty repo
        empty_repo = git.Repo.init(tmp_path)
        engine = GraphLayoutEngine(empty_repo)
        graph = engine.build_graph(max_commits=10)
        # Should not crash, just have no commits
        assert len(graph.commits) == 0
        assert graph.max_lanes == 1


class TestMultiLaneRendering:
    """Test suite for multi-lane graph rendering."""
    
    @pytest.fixture
    def simple_commit(self):
        """Create a simple test commit."""
        return CommitNode(
            sha="abc123def456",
            short_sha="abc123d",
            message="Test commit",
            full_message="Test commit\n\nFull message",
            author="Test Author",
            author_email="test@example.com",
            committer="Test Author",
            date=datetime.now(),
            parent_shas=["parent1"],
            lane=0,
            active_lanes=set(),
            commit_type=CommitType.NORMAL,
        )
    
    @pytest.fixture
    def merge_commit(self):
        """Create a test merge commit."""
        return CommitNode(
            sha="merge123def456",
            short_sha="merge12",
            message="Merge branch 'feature'",
            full_message="Merge branch 'feature'",
            author="Test Author",
            author_email="test@example.com",
            committer="Test Author",
            date=datetime.now(),
            parent_shas=["parent1", "parent2"],
            lane=0,
            active_lanes={1},
            merge_source_lanes=[1],
            commit_type=CommitType.MERGE,
        )
    
    @pytest.fixture
    def graph_with_lanes(self):
        """Create a test graph with multiple lanes."""
        graph = CommitGraph()
        graph.max_lanes = 3
        return graph
    
    def test_renderer_initialization_with_graph(self, graph_with_lanes):
        """Test that renderer initializes with graph context."""
        renderer = GitGraphRenderer(graph=graph_with_lanes)
        assert renderer.graph == graph_with_lanes
        assert renderer.get_max_lanes() == 3
    
    def test_renderer_initialization_without_graph(self):
        """Test that renderer works without graph (defaults)."""
        renderer = GitGraphRenderer()
        assert renderer.graph is None
        assert renderer.get_max_lanes() == 1
    
    def test_set_graph(self, graph_with_lanes):
        """Test setting graph after initialization."""
        renderer = GitGraphRenderer()
        assert renderer.get_max_lanes() == 1
        renderer.set_graph(graph_with_lanes)
        assert renderer.get_max_lanes() == 3
    
    def test_get_color_for_lane(self, graph_with_lanes):
        """Test that colors are assigned per lane."""
        renderer = GitGraphRenderer(graph=graph_with_lanes)
        color0 = renderer.get_color_for_lane(0)
        color1 = renderer.get_color_for_lane(1)
        assert color0 != color1
        # Colors should wrap around
        color_wrapped = renderer.get_color_for_lane(len(renderer.default_colors))
        assert color_wrapped == renderer.get_color_for_lane(0)
    
    def test_build_graph_columns_single_lane(self, simple_commit):
        """Test graph column building for single lane."""
        renderer = GitGraphRenderer()
        columns = renderer._build_graph_columns(simple_commit)
        # Should contain commit dot
        assert "●" in columns or renderer.COMMIT_DOT in renderer._strip_markup(columns)
    
    def test_build_graph_columns_multi_lane(self, simple_commit, graph_with_lanes):
        """Test graph column building for multiple lanes."""
        renderer = GitGraphRenderer(graph=graph_with_lanes)
        simple_commit.lane = 1
        simple_commit.active_lanes = {0, 2}
        
        columns = renderer._build_graph_columns(simple_commit)
        stripped = renderer._strip_markup(columns)
        
        # Should have vertical lines for lanes 0 and 2, commit dot for lane 1
        assert renderer.VERTICAL_LINE in stripped
        assert renderer.COMMIT_DOT in stripped
    
    def test_merge_commit_uses_diamond(self, merge_commit):
        """Test that merge commits use diamond symbol."""
        renderer = GitGraphRenderer()
        columns = renderer._build_graph_columns(merge_commit)
        stripped = renderer._strip_markup(columns)
        assert renderer.MERGE_DOT in stripped
    
    def test_merge_source_lanes_show_merge_indicator(self, merge_commit, graph_with_lanes):
        """Test that merge source lanes show merge indicator."""
        renderer = GitGraphRenderer(graph=graph_with_lanes)
        merge_commit.lane = 0
        merge_commit.active_lanes = {1}
        merge_commit.merge_source_lanes = [1]
        
        columns = renderer._build_graph_columns(merge_commit)
        stripped = renderer._strip_markup(columns)
        
        # Should have merge indicator in lane 1
        assert renderer.MERGE_LEFT in stripped or renderer.MERGE_DOT in stripped
    
    def test_render_commit_line_contains_sha(self, simple_commit):
        """Test that rendered line contains commit SHA."""
        renderer = GitGraphRenderer()
        line = renderer.render_commit_line(simple_commit)
        assert "abc123d" in line
    
    def test_render_commit_line_contains_message(self, simple_commit):
        """Test that rendered line contains commit message."""
        renderer = GitGraphRenderer()
        line = renderer.render_commit_line(simple_commit)
        assert "Test" in line
    
    def test_render_commit_line_handles_invalid_commit(self):
        """Test that renderer handles invalid commit gracefully."""
        renderer = GitGraphRenderer()
        line = renderer.render_commit_line(None)
        assert "error" in line.lower() or "invalid" in line.lower()
    
    def test_strip_markup_removes_colors(self):
        """Test that strip_markup removes Rich color markup."""
        renderer = GitGraphRenderer()
        marked_up = "[#ff0000]red text[/#ff0000]"
        stripped = renderer._strip_markup(marked_up)
        assert stripped == "red text"
        assert "#" not in stripped
    
    def test_real_repo_rendering(self):
        """Test rendering with real repository commits."""
        repo = git.Repo(".")
        engine = GraphLayoutEngine(repo)
        graph = engine.build_graph(max_commits=10)
        
        renderer = GitGraphRenderer(graph=graph)
        commits = graph.get_commits_in_order()
        
        for commit in commits:
            line = renderer.render_commit_line(commit)
            # Line should be non-empty and contain the SHA
            assert len(line) > 0
            assert commit.short_sha[:7] in line
