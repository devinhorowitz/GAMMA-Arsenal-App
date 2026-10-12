"""The LuaJIT the tests and the build run: 2.0, as the game embeds LuaJIT 2.0.4.

LuaJIT 2.1 walks tables in a different order and has library functions 2.0 lacks, so a test
under 2.1 can pass code the game would fail. A lupa built without 2.0 falls back to 2.1, and
says so.

    from lua_jit import L
"""
import sys

try:
    import lupa.luajit20 as L
except ImportError:
    import lupa.luajit21 as L
    sys.stderr.write("lupa has no LuaJIT 2.0; running 2.1, not the game's 2.0.4\n")
