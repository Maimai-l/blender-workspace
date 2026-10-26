using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace WordDefense.Data
{
    /// <summary>
    /// Minimal read-only reader for SQLite 3 database files (UTF-8, rollback journal). It walks table B-trees
    /// directly, so the game can read vocabulary.db on any platform without a native SQLite library.
    /// Supports interior/leaf table pages and overflow chains; indexes are not needed and not read.
    /// </summary>
    public sealed class SqliteReader
    {
        readonly byte[] db;
        readonly int pageSize;
        readonly int usable;

        public SqliteReader(byte[] data)
        {
            db = data;
            if (data.Length < 100 || Encoding.ASCII.GetString(data, 0, 15) != "SQLite format 3")
                throw new InvalidDataException("not a SQLite 3 database");
            int ps = (data[16] << 8) | data[17];
            pageSize = ps == 1 ? 65536 : ps;
            usable = pageSize - data[20];
            int enc = BE32(data, 56);
            if (enc != 0 && enc != 1) throw new NotSupportedException("only UTF-8 databases are supported (encoding " + enc + ")");
        }

        public static SqliteReader Open(string path)
        {
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                var buf = new byte[fs.Length];
                int off = 0;
                while (off < buf.Length)
                {
                    int n = fs.Read(buf, off, buf.Length - off);
                    if (n <= 0) break;
                    off += n;
                }
                return new SqliteReader(buf);
            }
        }

        public int PageSize { get { return pageSize; } }
        public int PageCount { get { return db.Length / pageSize; } }

        // ------------------------------------------------------------ primitives
        internal static int BE16(byte[] b, int o) { return (b[o] << 8) | b[o + 1]; }
        internal static int BE32(byte[] b, int o) { return (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]; }

        internal static long Varint(byte[] b, int o, out int len)
        {
            long v = 0;
            for (int i = 0; i < 8; i++)
            {
                byte x = b[o + i];
                v = (v << 7) | (long)(x & 0x7f);
                if ((x & 0x80) == 0) { len = i + 1; return v; }
            }
            v = (v << 8) | b[o + 8];
            len = 9;
            return v;
        }

        // ------------------------------------------------------------ schema
        public sealed class TableInfo
        {
            public string Name;
            public int RootPage;
            public string Sql;
            public List<string> Columns = new List<string>();
            public int IntegerPrimaryKey = -1;   // column stored as the rowid (NULL in the record)

            public int Col(string name)
            {
                for (int i = 0; i < Columns.Count; i++)
                    if (string.Equals(Columns[i], name, StringComparison.OrdinalIgnoreCase)) return i;
                return -1;
            }
        }

        public TableInfo GetTable(string name)
        {
            TableInfo found = null;
            Walk(1, row =>
            {
                if (found != null) return;
                if (row.GetText(0) == "table" && string.Equals(row.GetText(1), name, StringComparison.OrdinalIgnoreCase))
                {
                    found = new TableInfo { Name = row.GetText(1), RootPage = (int)row.GetInt(3), Sql = row.GetText(4) };
                    ParseColumns(found);
                }
            });
            return found;
        }

        public List<string> TableNames()
        {
            var names = new List<string>();
            Walk(1, row => { if (row.GetText(0) == "table") names.Add(row.GetText(1)); });
            return names;
        }

        static void ParseColumns(TableInfo t)
        {
            // strip "-- comments" and split the column list at top-level commas
            var sb = new StringBuilder();
            foreach (var line in t.Sql.Split('\n'))
            {
                int c = line.IndexOf("--", StringComparison.Ordinal);
                sb.Append(c >= 0 ? line.Substring(0, c) : line).Append(' ');
            }
            string sql = sb.ToString();
            int open = sql.IndexOf('('), close = sql.LastIndexOf(')');
            if (open < 0 || close <= open) return;
            string body = sql.Substring(open + 1, close - open - 1);
            var parts = new List<string>();
            int depth = 0, start = 0;
            for (int i = 0; i < body.Length; i++)
            {
                char ch = body[i];
                if (ch == '(') depth++;
                else if (ch == ')') depth--;
                else if (ch == ',' && depth == 0) { parts.Add(body.Substring(start, i - start)); start = i + 1; }
            }
            parts.Add(body.Substring(start));
            foreach (var raw in parts)
            {
                string p = raw.Trim();
                if (p.Length == 0) continue;
                string upper = p.ToUpperInvariant();
                if (upper.StartsWith("UNIQUE") || upper.StartsWith("PRIMARY KEY") || upper.StartsWith("CONSTRAINT") ||
                    upper.StartsWith("CHECK") || upper.StartsWith("FOREIGN KEY")) continue;
                string colName = p.Split(new[] { ' ', '\t', '\r' }, StringSplitOptions.RemoveEmptyEntries)[0].Trim('"', '`', '[', ']');
                if (upper.Contains("INTEGER PRIMARY KEY")) t.IntegerPrimaryKey = t.Columns.Count;
                t.Columns.Add(colName);
            }
        }

        // ------------------------------------------------------------ rows
        public sealed class Row
        {
            readonly byte[] b;
            readonly int start;
            public readonly long RowId;
            int[] types;
            int[] offsets;
            internal int IntegerPrimaryKey = -1;

            internal Row(byte[] buffer, int offset, long rowId)
            {
                b = buffer; start = offset; RowId = rowId;
            }

            void Header()
            {
                if (types != null) return;
                int l;
                long hsize = Varint(b, start, out l);
                int p = start + l, end = start + (int)hsize;
                var t = new List<int>(16);
                while (p < end)
                {
                    t.Add((int)Varint(b, p, out l));
                    p += l;
                }
                types = t.ToArray();
                offsets = new int[types.Length];
                int body = end;
                for (int i = 0; i < types.Length; i++)
                {
                    offsets[i] = body;
                    body += SerialSize(types[i]);
                }
            }

            static int SerialSize(int st)
            {
                switch (st)
                {
                    case 0: case 8: case 9: case 10: case 11: return 0;
                    case 1: return 1;
                    case 2: return 2;
                    case 3: return 3;
                    case 4: return 4;
                    case 5: return 6;
                    case 6: case 7: return 8;
                    default: return st >= 12 ? (st - (st % 2 == 0 ? 12 : 13)) / 2 : 0;
                }
            }

            public int ColumnCount { get { Header(); return types.Length; } }

            public bool IsNull(int col)
            {
                Header();
                if (col == IntegerPrimaryKey) return false;
                return col >= types.Length || types[col] == 0;
            }

            public long GetInt(int col)
            {
                Header();
                if (col == IntegerPrimaryKey) return RowId;
                if (col >= types.Length) return 0;
                int st = types[col], o = offsets[col];
                switch (st)
                {
                    case 0: return 0;
                    case 8: return 0;
                    case 9: return 1;
                    case 7: return (long)GetDouble(col);
                    case 1: return (sbyte)b[o];
                    case 2: return (short)((b[o] << 8) | b[o + 1]);
                    case 3: { int v = (b[o] << 16) | (b[o + 1] << 8) | b[o + 2]; if ((v & 0x800000) != 0) v |= unchecked((int)0xFF000000); return v; }
                    case 4: return BE32(b, o);
                    case 5: { long v = 0; for (int i = 0; i < 6; i++) v = (v << 8) | b[o + i]; if ((v & 0x800000000000L) != 0) v |= unchecked((long)0xFFFF000000000000UL); return v; }
                    case 6: { long v = 0; for (int i = 0; i < 8; i++) v = (v << 8) | b[o + i]; return v; }
                    default:
                        long parsed;
                        return long.TryParse(GetText(col), out parsed) ? parsed : 0;
                }
            }

            public double GetDouble(int col)
            {
                Header();
                if (col == IntegerPrimaryKey) return RowId;
                if (col >= types.Length) return 0;
                int st = types[col], o = offsets[col];
                if (st == 7)
                {
                    long bits = 0;
                    for (int i = 0; i < 8; i++) bits = (bits << 8) | b[o + i];
                    return BitConverter.Int64BitsToDouble(bits);
                }
                if (st >= 1 && st <= 9) return GetInt(col);
                if (st >= 13)
                {
                    double d;
                    return double.TryParse(GetText(col), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d) ? d : 0;
                }
                return 0;
            }

            public string GetText(int col)
            {
                Header();
                if (col == IntegerPrimaryKey) return RowId.ToString();
                if (col >= types.Length) return null;
                int st = types[col];
                if (st == 0) return null;
                if (st >= 13 && st % 2 == 1) return Encoding.UTF8.GetString(b, offsets[col], (st - 13) / 2);
                if (st >= 12) return Convert.ToBase64String(b, offsets[col], (st - 12) / 2);
                if (st == 7) return GetDouble(col).ToString(System.Globalization.CultureInfo.InvariantCulture);
                return GetInt(col).ToString();
            }
        }

        /// <summary>Visits every row of a table in rowid order.</summary>
        public void ForEachRow(TableInfo table, Action<Row> visit)
        {
            int ipk = table.IntegerPrimaryKey;
            Walk(table.RootPage, r => { r.IntegerPrimaryKey = ipk; visit(r); });
        }

        void Walk(int rootPage, Action<Row> visit)
        {
            var stack = new Stack<int>();
            stack.Push(rootPage);
            int guard = 0;
            while (stack.Count > 0)
            {
                if (++guard > 10000000) throw new InvalidDataException("b-tree walk did not terminate");
                int pg = stack.Pop();
                int off = (pg - 1) * pageSize;
                int hdr = off + (pg == 1 ? 100 : 0);
                if (hdr + 8 > db.Length) throw new InvalidDataException("page " + pg + " out of range");
                byte type = db[hdr];
                int ncells = BE16(db, hdr + 3);
                if (type == 0x05)
                {
                    // interior table page: children in key order, right-most pointer last
                    stack.Push(BE32(db, hdr + 8));
                    for (int i = ncells - 1; i >= 0; i--)
                    {
                        int cp = off + BE16(db, hdr + 12 + 2 * i);
                        stack.Push(BE32(db, cp));
                    }
                }
                else if (type == 0x0D)
                {
                    for (int i = 0; i < ncells; i++)
                    {
                        int cp = off + BE16(db, hdr + 8 + 2 * i);
                        int l1, l2;
                        long payload = Varint(db, cp, out l1);
                        long rowid = Varint(db, cp + l1, out l2);
                        int p = cp + l1 + l2;
                        int x = usable - 35;
                        if (payload <= x)
                        {
                            visit(new Row(db, p, rowid));
                            continue;
                        }
                        int m = ((usable - 12) * 32 / 255) - 23;
                        int k = m + (int)((payload - m) % (usable - 4));
                        int local = k <= x ? k : m;
                        var buf = new byte[payload];
                        Buffer.BlockCopy(db, p, buf, 0, local);
                        int got = local;
                        int ovf = BE32(db, p + local);
                        while (ovf != 0 && got < payload)
                        {
                            int po = (ovf - 1) * pageSize;
                            int next = BE32(db, po);
                            int n = (int)Math.Min(usable - 4, payload - got);
                            Buffer.BlockCopy(db, po + 4, buf, got, n);
                            got += n;
                            ovf = next;
                        }
                        visit(new Row(buf, 0, rowid));
                    }
                }
                else
                {
                    throw new InvalidDataException("unexpected b-tree page type " + type + " on page " + pg);
                }
            }
        }
    }
}
