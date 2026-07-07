/*
 * makruk_selftest.cpp
 * Standalone Phase 3/4 rule tester for Makruk. Links ONLY the game-logic layer
 * (board / boardhistory / gamelogic / rules + core utils) - no neural net, no search,
 * no GPU. Lets us prove legality / movegen / terminals before any training.
 *
 * Build: see scripts_makruk/build_selftest.sh
 */

#include <cstdlib>
#include <iostream>
#include <vector>

#include "../core/global.h"
#include "../core/rand.h"
#include "../game/board.h"
#include "../game/boardhistory.h"
#include "../game/gamelogic.h"
#include "../game/rules.h"

using namespace std;

static int g_failures = 0;
static void check(bool cond, const string& what) {
  if(!cond) {
    cout << "  [FAIL] " << what << "\n";
    g_failures++;
  } else {
    cout << "  [ok]   " << what << "\n";
  }
}

// Collect every legal Loc for the side to move in the current (board, stage).
static vector<Loc> legalLocs(const Board& board, const BoardHistory& hist) {
  vector<Loc> out;
  Player pla = board.nextPla;
  for(int y = 0; y < board.y_size; y++)
    for(int x = 0; x < board.x_size; x++) {
      Loc loc = Location::getLoc(x, y, board.x_size);
      if(hist.isLegal(board, loc, pla))
        out.push_back(loc);
    }
  return out;
}

// Count distinct legal FULL moves (from-square, to-square) for the side to move at stage 0.
static int countLegalFullMoves(const Board& board, const BoardHistory& hist) {
  int total = 0;
  vector<Loc> froms = legalLocs(board, hist);
  for(Loc from : froms) {
    Board b = board;
    BoardHistory h = hist;
    h.makeBoardMoveAssumeLegal(b, from, b.nextPla);  // stage 0 -> 1
    total += (int)legalLocs(b, h).size();
  }
  return total;
}

static void testStartPosition() {
  cout << "== Test: start position ==\n";
  Board board;
  BoardHistory hist(board, board.nextPla, Rules());

  cout << Board::toStringSimple(board, '\n') << "\n";

  check(board.x_size == 8 && board.y_size == 8, "board is 8x8");
  check(board.numStonesOnBoard() == 32, "32 pieces on the board at start");
  check(board.numPlaStonesOnBoard(P_BLACK) == 16, "first mover has 16 pieces");
  check(board.numPlaStonesOnBoard(P_WHITE) == 16, "second player has 16 pieces");
  check(!GameLogic::isInCheck(board, P_BLACK), "first mover not in check at start");
  check(!GameLogic::isInCheck(board, P_WHITE), "second player not in check at start");

  int fullMoves = countLegalFullMoves(board, hist);
  cout << "  legal full moves from start = " << fullMoves << " (expected 23)\n";
  check(fullMoves == 23, "23 legal opening moves");
}

// Play one full move chosen uniformly at random from the legal set. Returns false if the
// game ended. Asserts legality and board consistency at every half-move.
static bool playRandomFullMove(Board& board, BoardHistory& hist, Rand& rng) {
  for(int half = 0; half < 2; half++) {
    if(hist.isGameFinished)
      return false;
    vector<Loc> legal = legalLocs(board, hist);
    if(legal.empty()) {
      cout << "  [FAIL] no legal move but game not flagged finished (stage "
           << board.stage << ")\n";
      g_failures++;
      return false;
    }
    Loc pick = legal[rng.nextUInt((uint32_t)legal.size())];
    // Re-verify legality through the single gate before committing.
    if(!hist.isLegal(board, pick, board.nextPla)) {
      cout << "  [FAIL] picked an illegal move\n";
      g_failures++;
      return false;
    }
    hist.makeBoardMoveAssumeLegal(board, pick, board.nextPla);
    board.checkConsistency();
    // Kings must never be captured in legal play.
    if(GameLogic::findKing(board, P_BLACK) == Board::NULL_LOC ||
       GameLogic::findKing(board, P_WHITE) == Board::NULL_LOC) {
      cout << "  [FAIL] a king disappeared from the board\n";
      g_failures++;
      return false;
    }
  }
  return !hist.isGameFinished;
}

static void testRandomSelfPlay(int games, int maxFullMoves) {
  cout << "== Test: random legal self-play stress (" << games << " games) ==\n";
  Rand rng("makruk-selftest-seed");
  int finished = 0, draws = 0, blackWins = 0, whiteWins = 0, hitCap = 0;
  for(int g = 0; g < games; g++) {
    Board board;
    Rules rules;
    rules.maxmovesNoCapture = 200;  // safety cap for the stress test
    BoardHistory hist(board, board.nextPla, rules);
    int mv = 0;
    while(mv < maxFullMoves && !hist.isGameFinished) {
      if(!playRandomFullMove(board, hist, rng))
        break;
      mv++;
    }
    if(hist.isGameFinished) {
      finished++;
      if(hist.winner == C_EMPTY) draws++;
      else if(hist.winner == P_BLACK) blackWins++;
      else if(hist.winner == P_WHITE) whiteWins++;
    } else {
      hitCap++;
    }
  }
  cout << "  finished=" << finished << " (B=" << blackWins << " W=" << whiteWins
       << " draw=" << draws << "), hitMoveCap=" << hitCap << "\n";
  check(g_failures == 0, "no illegal states across all random games");
}

//----------------------------------------------------------------------------------------
// Phase 4: dedicated per-rule unit tests
//----------------------------------------------------------------------------------------

static Loc L(int x, int y) { return Location::getLoc(x, y, 8); }

static Board setupEmpty(Player pla) {
  Board b;
  b.setFEN("8/8/8/8/8/8/8/8", pla);
  return b;
}
static void put(Board& b, int x, int y, Player pla, Color type) {
  b.setStone(L(x, y), getPiece(pla, type));
}

// Legal to-squares for the piece standing on 'from' (drives stage 0 then enumerates stage 1).
static vector<Loc> legalDestsFrom(const Board& board, const BoardHistory& hist, Loc from) {
  vector<Loc> out;
  if(!hist.isLegal(board, from, board.nextPla))
    return out;  // piece not selectable (no king-safe move)
  Board b = board;
  BoardHistory h = hist;
  h.makeBoardMoveAssumeLegal(b, from, b.nextPla);  // stage 0 -> 1, same player
  for(int y = 0; y < b.y_size; y++)
    for(int x = 0; x < b.x_size; x++) {
      Loc loc = L(x, y);
      if(h.isLegal(b, loc, b.nextPla))
        out.push_back(loc);
    }
  return out;
}
static bool hasDest(const vector<Loc>& v, int x, int y) {
  Loc t = L(x, y);
  for(Loc l : v)
    if(l == t)
      return true;
  return false;
}

static void testPieceMovement() {
  cout << "== Test: per-piece movement ==\n";
  // Rook in the centre of an empty board: 14 moves.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_ROOK);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.size() == 14, "rook on d4 (empty board) has 14 moves");
  }
  // Knight in the centre: 8 leaps.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_KNIGHT);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.size() == 8, "knight on d4 has 8 moves");
  }
  // Met: 4 diagonals only.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_MET);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.size() == 4 && hasDest(d, 2, 2) && hasDest(d, 4, 4) && !hasDest(d, 3, 4) &&
            !hasDest(d, 4, 3),
          "met on d4 has exactly 4 diagonal moves");
  }
  // Khon is directional: 4 diagonals + ONE straight forward (not backward).
  {
    Board b = setupEmpty(P_BLACK);  // P_BLACK forward = +y
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_KHON);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.size() == 5 && hasDest(d, 3, 4) && !hasDest(d, 3, 2),
          "black khon: 5 moves, forward (+y) yes, backward-straight no");
  }
  {
    Board b = setupEmpty(P_WHITE);  // P_WHITE forward = -y
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_WHITE, C_KHON);
    BoardHistory h(b, P_WHITE, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.size() == 5 && hasDest(d, 3, 2) && !hasDest(d, 3, 4),
          "white khon: 5 moves, forward (-y) yes, backward-straight no");
  }
}

static void testBia() {
  cout << "== Test: Bia (pawn) ==\n";
  // No initial double-step: a Bia has exactly one push square.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 2, P_BLACK, C_BIA);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 2));
    check(d.size() == 1 && hasDest(d, 3, 3), "black bia pushes one square only (no double-step)");
  }
  // Push blocked, no diagonal enemies -> no moves.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_BIA);
    put(b, 3, 4, P_WHITE, C_ROOK);  // blocks the push
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.empty(), "blocked bia with no diagonal target cannot move (no straight capture)");
  }
  // Diagonal captures + push.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_BIA);
    put(b, 2, 4, P_WHITE, C_ROOK);
    put(b, 4, 4, P_WHITE, C_KNIGHT);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(3, 3));
    check(d.size() == 3 && hasDest(d, 3, 4) && hasDest(d, 2, 4) && hasDest(d, 4, 4),
          "bia: forward push + two diagonal captures");
  }
}

static void testPromotion() {
  cout << "== Test: promotion ==\n";
  // Black promotes on rank y=5 by pushing.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 4, P_BLACK, C_BIA);
    BoardHistory h(b, P_BLACK, Rules());
    h.makeBoardMoveAssumeLegal(b, L(3, 4), P_BLACK);
    h.makeBoardMoveAssumeLegal(b, L(3, 5), P_BLACK);
    check(getPieceType(b.colors[L(3, 5)]) == C_BIAGAE, "black bia promotes on push to rank 6");
  }
  // Black promotes by capturing onto the promotion rank.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 4, P_BLACK, C_BIA);
    put(b, 4, 5, P_WHITE, C_ROOK);
    BoardHistory h(b, P_BLACK, Rules());
    h.makeBoardMoveAssumeLegal(b, L(3, 4), P_BLACK);
    h.makeBoardMoveAssumeLegal(b, L(4, 5), P_BLACK);
    check(getPieceType(b.colors[L(4, 5)]) == C_BIAGAE, "black bia promotes on capture onto rank 6");
  }
  // White promotes on rank y=2.
  {
    Board b = setupEmpty(P_WHITE);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_WHITE, C_BIA);
    BoardHistory h(b, P_WHITE, Rules());
    h.makeBoardMoveAssumeLegal(b, L(3, 3), P_WHITE);
    h.makeBoardMoveAssumeLegal(b, L(3, 2), P_WHITE);
    check(getPieceType(b.colors[L(3, 2)]) == C_BIAGAE, "white bia promotes on push to rank 3");
  }
  // No premature promotion.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 3, 3, P_BLACK, C_BIA);
    BoardHistory h(b, P_BLACK, Rules());
    h.makeBoardMoveAssumeLegal(b, L(3, 3), P_BLACK);
    h.makeBoardMoveAssumeLegal(b, L(3, 4), P_BLACK);
    check(getPieceType(b.colors[L(3, 4)]) == C_BIA, "bia not promoted before reaching the promo rank");
  }
}

static void testKingSafety() {
  cout << "== Test: check, pins, king safety ==\n";
  // Pinned rook may only move along the pin file.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 0, 3, P_BLACK, C_ROOK);   // pinned on file x=0
    put(b, 0, 7, P_WHITE, C_ROOK);   // pinner
    put(b, 7, 7, P_WHITE, C_KING);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(0, 3));
    bool allOnFile = true;
    for(Loc l : d)
      if(Location::getX(l, 8) != 0)
        allOnFile = false;
    check(!d.empty() && allOnFile && !hasDest(d, 1, 3),
          "pinned rook may only move along the pin file");
  }
  // King may not step into an attacked square.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 5, 1, P_WHITE, C_ROOK);   // controls rank y=1
    put(b, 7, 7, P_WHITE, C_KING);
    BoardHistory h(b, P_BLACK, Rules());
    auto d = legalDestsFrom(b, h, L(0, 0));
    check(!hasDest(d, 0, 1) && !hasDest(d, 1, 1) && hasDest(d, 1, 0),
          "king cannot move onto attacked squares, only the safe one");
  }
}

static void testCheckmateStalemate() {
  cout << "== Test: checkmate & stalemate ==\n";
  // Two-rook mate, White to move, already mated (predicate level).
  {
    Board b = setupEmpty(P_WHITE);
    put(b, 0, 7, P_WHITE, C_KING);
    put(b, 4, 0, P_BLACK, C_KING);
    put(b, 7, 7, P_BLACK, C_ROOK);
    put(b, 7, 6, P_BLACK, C_ROOK);
    check(GameLogic::isInCheck(b, P_WHITE) && !GameLogic::hasAnyLegalMove(b, P_WHITE),
          "two-rook position is checkmate for White (in check, no moves)");
  }
  // Integration: Black plays the mating move; game ends with Black winner.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 7, P_WHITE, C_KING);
    put(b, 4, 0, P_BLACK, C_KING);
    put(b, 7, 6, P_BLACK, C_ROOK);
    put(b, 5, 5, P_BLACK, C_ROOK);
    BoardHistory h(b, P_BLACK, Rules());
    h.makeBoardMoveAssumeLegal(b, L(5, 5), P_BLACK);
    h.makeBoardMoveAssumeLegal(b, L(5, 7), P_BLACK);  // Rook to 7th rank: mate
    check(h.isGameFinished && h.winner == P_BLACK, "rook move delivers checkmate, Black wins");
  }
  // Stalemate predicate: White to move, not in check, no legal move.
  {
    Board b = setupEmpty(P_WHITE);
    put(b, 0, 7, P_WHITE, C_KING);
    put(b, 2, 6, P_BLACK, C_KING);
    put(b, 1, 6, P_BLACK, C_ROOK);  // defended by the black king
    check(!GameLogic::isInCheck(b, P_WHITE) && !GameLogic::hasAnyLegalMove(b, P_WHITE),
          "position is stalemate for White (not in check, no moves)");
  }
  // Integration: Black move produces stalemate -> draw.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 7, P_WHITE, C_KING);
    put(b, 2, 6, P_BLACK, C_KING);
    put(b, 1, 3, P_BLACK, C_ROOK);
    BoardHistory h(b, P_BLACK, Rules());
    h.makeBoardMoveAssumeLegal(b, L(1, 3), P_BLACK);
    h.makeBoardMoveAssumeLegal(b, L(1, 6), P_BLACK);
    check(h.isGameFinished && h.winner == C_EMPTY, "stalemating move ends the game as a draw");
  }
}

static void testCheckNotMate() {
  cout << "== Test: check-with-escape is NOT mate; material-up is NOT terminal ==\n";
  // White king e1 in check from black rook e8; d1/d2/f1/f2 escapes exist.
  {
    Board b = setupEmpty(P_WHITE);
    put(b, 4, 0, P_BLACK, C_ROOK);  // rook e8 (y=0 is FEN rank 8 side for P_BLACK here)
    put(b, 4, 7, P_WHITE, C_KING);  // king e1
    put(b, 0, 0, P_BLACK, C_KING);
    check(GameLogic::isInCheck(b, P_WHITE), "rook check detected");
    check(GameLogic::hasAnyLegalMove(b, P_WHITE), "checked king HAS legal escapes");
    BoardHistory h(b, P_WHITE, Rules());
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_BLACK, L(4, 0)) == C_WALL,
          "check with escape -> game continues (not mate, not terminal)");
  }
  // Big material advantage alone is never terminal.
  {
    Board b = setupEmpty(P_WHITE);
    put(b, 0, 0, P_BLACK, C_KING);
    put(b, 3, 3, P_BLACK, C_ROOK);
    put(b, 4, 3, P_BLACK, C_ROOK);
    put(b, 3, 4, P_BLACK, C_KNIGHT);
    put(b, 7, 7, P_WHITE, C_KING);
    put(b, 6, 6, P_WHITE, C_MET);   // weak side has 2 pieces -> counting not active
    BoardHistory h(b, P_WHITE, Rules());
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_BLACK, L(3, 3)) == C_WALL,
          "material-up (R+R+N vs M) is NOT a win by itself - game continues");
  }
}

static void testCounting() {
  cout << "== Test: pieces' honour counting ==\n";
  // K+R vs lone K. One rook -> limit 16 full moves; total pieces 3 -> 2*(16-3)=26 plies.
  // Black is the lone king (to move), not in check and with legal moves, so the only
  // terminal condition in play is the counting draw, governed by board.movenumslc.
  auto kingRookVsKing = [](int movenumslc) {
    Board b = setupEmpty(P_BLACK);  // black (lone king) to move
    put(b, 0, 0, P_WHITE, C_KING);
    put(b, 2, 2, P_WHITE, C_ROOK);
    put(b, 4, 4, P_BLACK, C_KING);
    BoardHistory h(b, P_BLACK, Rules());
    b.movenumslc = movenumslc;
    return GameLogic::checkWinnerAfterPlayed(b, h, P_WHITE, L(2, 2));
  };
  // True Thai rule: budget = limit - pieces. K+R vs K: 16-3=13 moves = 26 plies.
  check(kingRookVsKing(20) == C_WALL, "K+R vs K under the count -> game continues");
  check(kingRookVsKing(25) == C_WALL, "K+R vs K one ply before the count -> continues");
  check(kingRookVsKing(26) == C_EMPTY, "K+R vs K at the count limit (26 plies) -> draw");
  check(kingRookVsKing(50) == C_EMPTY, "K+R vs K past the count -> draw");

  // K + single Knight vs K: 1 Ma -> limit 64 -> 2*(64-3)=122 plies before the draw.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_WHITE, C_KING);
    put(b, 2, 0, P_WHITE, C_KNIGHT);
    put(b, 4, 4, P_BLACK, C_KING);
    BoardHistory h(b, P_BLACK, Rules());
    b.movenumslc = 100;
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_WHITE, L(2, 0)) == C_WALL,
          "K+Ma vs K under 122-ply count -> continues");
    b.movenumslc = 122;  // 2*(64-3)
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_WHITE, L(2, 0)) == C_EMPTY,
          "K+Ma vs K at 122-ply count -> draw");
  }

  // Board's honour: no Bia on either side, defender NOT lone -> 64 moves (128 plies).
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_WHITE, C_KING);
    put(b, 2, 2, P_WHITE, C_ROOK);
    put(b, 4, 4, P_BLACK, C_KING);
    put(b, 6, 6, P_BLACK, C_MET);
    BoardHistory h(b, P_BLACK, Rules());
    b.movenumslc = 127;
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_WHITE, L(2, 2)) == C_WALL,
          "board honour: under 128 plies -> continues");
    b.movenumslc = 128;
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_WHITE, L(2, 2)) == C_EMPTY,
          "board honour: no-Bia 128 plies -> draw");
  }

  // K + Met (no Rua/Khon/Ma) vs K: cannot force mate -> immediate draw regardless of count.
  {
    Board b = setupEmpty(P_BLACK);
    put(b, 0, 0, P_WHITE, C_KING);
    put(b, 2, 2, P_WHITE, C_MET);
    put(b, 4, 4, P_BLACK, C_KING);
    BoardHistory h(b, P_BLACK, Rules());
    b.movenumslc = 0;
    check(GameLogic::checkWinnerAfterPlayed(b, h, P_WHITE, L(2, 2)) == C_EMPTY,
          "K+Met vs K (no mating piece) -> immediate draw");
  }
}

static void testFENRoundTrip() {
  cout << "== Test: FEN round-trip ==\n";
  Board a;  // start position
  string fen = a.getFEN();
  Board b;
  bool ok = b.setFEN(fen);
  check(ok && a.isEqualForTesting(b), "start position survives getFEN -> setFEN");
}

int main(int argc, char** argv) {
  std::cout << std::unitbuf;  // unbuffered, so a crash still shows where we were
  Board::initHash();

  int games = (argc > 1) ? atoi(argv[1]) : 2000;
  int maxFullMoves = (argc > 2) ? atoi(argv[2]) : 400;

  testStartPosition();
  testPieceMovement();
  testBia();
  testPromotion();
  testKingSafety();
  testCheckmateStalemate();
  testCheckNotMate();
  testCounting();
  testFENRoundTrip();
  testRandomSelfPlay(games, maxFullMoves);

  cout << "\n=== " << (g_failures == 0 ? "ALL CHECKS PASSED" : "FAILURES PRESENT") << " ("
       << g_failures << " failures) ===\n";
  return g_failures == 0 ? 0 : 1;
}
