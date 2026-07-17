#include <cassert>
#include <iostream>
#include "../core/global.h"
#include "../core/rand.h"
#include "../game/board.h"
#include "../game/boardhistory.h"
#include "../game/gamelogic.h"
#include "../game/rules.h"
using namespace std;

static int fails = 0;
static void check(bool c, const string& what) {
  cout << (c ? "  [ok]   " : "  [FAIL] ") << what << endl;
  if(!c) fails++;
}

static GameLogic::ResultsBeforeNN probe(const string& fen, Player pla) {
  Board b;
  bool suc = b.setFEN(fen, pla);
  check(suc, "fen parsed: " + fen);
  Rules rules;
  BoardHistory hist(b, pla, rules);
  GameLogic::ResultsBeforeNN r;
  r.initFull(b, hist, pla);
  check(r.inited, "inited");
  return r;
}

int main() {
  Board::initHash();

  // def k(7,0), att K(7,2), R(2,5): R->(2,0) mates (back row, king boxes escapes)
  auto r1 = probe("7k/8/7K/8/8/2R5/8/8", P_BLACK);
  check(r1.winner == P_BLACK, "KRK mate-in-1 detected");

  // att king far away: rook check on y0 lets king escape via (6,1)/(7,1)
  auto r2 = probe("7k/8/8/8/8/5K2/8/R7", P_BLACK);
  check(r2.winner == C_WALL, "no false mate when king too far");

  // same mating position but lone king to move: defender can never mate
  auto r3 = probe("7k/8/7K/8/8/2R5/8/8", P_WHITE);
  check(r3.winner == C_WALL, "lone king to move: no mate claim");

  // open middlegame-like: gate should keep quiet (many pieces, no count)
  auto r4 = probe("rnskmsnr/8/pppppppp/8/8/PPPPPPPP/8/RNSKMSNR", P_BLACK);
  check(r4.winner == C_WALL, "full board: oracle gated off / no claim");

  cout << (fails ? "FAILURES" : "ALL_INITFULL_OK") << endl;
  return fails ? 1 : 0;
}
