package xqwlight;

public class Cli {
  private static String mvToCoord(int mv) {
    int src = Position.SRC(mv);
    int dst = Position.DST(mv);
    return sqToCoord(src) + sqToCoord(dst);
  }
  private static String sqToCoord(int sq) {
    int file = Position.FILE_X(sq) - Position.FILE_LEFT;
    int rank = Position.RANK_Y(sq) - Position.RANK_TOP;
    return "abcdefghi".charAt(file) + Integer.toString(rank);
  }
  public static void main(String[] args) throws Exception {
    if (args.length < 1) {
      System.err.println("usage: java xqwlight.Cli '<fen>' [depth] [millis]");
      System.exit(2);
    }
    String fen = args[0];
    int depth = args.length > 1 ? Integer.parseInt(args[1]) : 8;
    int millis = args.length > 2 ? Integer.parseInt(args[2]) : 1000;
    Position pos = new Position();
    pos.fromFen(fen);
    Search search = new Search(pos, 12);
    int mv = search.searchMain(depth, millis);
    if (mv <= 0) {
      System.out.println("nomove");
    } else {
      System.out.println(mvToCoord(mv));
    }
  }
}
