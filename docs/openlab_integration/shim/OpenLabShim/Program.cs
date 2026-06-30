// OpenLabShim - x86 / .NET Framework 4.8
//
// A persistent process that:
//   1. connects once to the OpenLab Acquisition session (expensive handshake),
//   2. takes instrument control,
//   3. reads newline-delimited commands from stdin and turns them into SDK calls,
//   4. emits responses (OK/ERR) and unsolicited async events (EVENT/RESULT) on stdout.
//
// ChromTroller (64-bit Python) launches this and talks to it like it talked to the
// Arduino. All instrument-internal IDs (module hashkeys, firmware strings, property
// ids) stay on this side; ChromTroller only ever uses logical names.
//
// Lines marked "TODO confirm" use member names taken from the SDK reference guide -
// verify them against your installed assembly version when you build.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

using Agilent.OpenLab.SharedServices;
using Agilent.OpenLAB.Acquisition.AutomationCore;
using Agilent.OpenLAB.Acquisition.AutomationInstrument;

namespace OpenLabShim
{
    internal class Program
    {
        // ---- runtime assembly resolution: find Agilent dependencies in the install dirs ----
        static readonly string[] ProbeDirs =
        {
            @"C:\Program Files (x86)\Agilent Technologies\OpenLab Acquisition",
            @"C:\Program Files (x86)\Agilent Technologies\OpenLab Services\Common",
        };

        static readonly object ConsoleLock = new object();

        static ShimConfig cfg;
        static IInstrumentController ic;
        static string valveModuleKey;

        // deep method-parameter overrides accumulated (per module hashkey) before START_RUN
        static readonly Dictionary<string, List<ResourceIdAndValue>> pending =
            new Dictionary<string, List<ResourceIdAndValue>>();

        static readonly AutoResetEvent appInit = new AutoResetEvent(false);
        static readonly AutoResetEvent stateRecv = new AutoResetEvent(false);

        static int Main(string[] args)
        {
            AppDomain.CurrentDomain.AssemblyResolve += Resolve;
            try
            {
                string cfgPath = args.Length > 0 ? args[0] : "shim.config.json";
                cfg = JsonConvert.DeserializeObject<ShimConfig>(File.ReadAllText(cfgPath));

                Connect();
                ic.TakeInstrumentControl();
                valveModuleKey = ResolveModuleKey(cfg.ValveModuleMatch);
                WireEvents();

                Emit("READY");
                DispatchLoop();
                return 0;
            }
            catch (Exception ex)
            {
                Emit("FATAL " + ex.Message);
                return 1;
            }
            finally
            {
                try { if (ic != null) ic.Disconnect(); } catch { /* best effort */ }
            }
        }

        static Assembly Resolve(object sender, ResolveEventArgs e)
        {
            string file = new AssemblyName(e.Name).Name + ".dll";
            foreach (var d in ProbeDirs)
            {
                string p = Path.Combine(d, file);
                if (File.Exists(p)) return Assembly.LoadFrom(p);
            }
            return null;
        }

        // ---------------------------------------------------------------- connection
        static void Connect()
        {
            // 1. Shared Services authentication -> security ticket.
            //    TODO confirm: exact member exposing the ticket string (Programmer's
            //    Guide, SharedServices). TicketContainer is the documented holder.
            var conn = new Connection(cfg.ConnectionString ?? "",
                                      cfg.Login, cfg.Domain, cfg.Password);
            string ticket = conn.TicketContainer.Ticket;   // TODO confirm member

            // 2. instrument + project GUIDs come from config (read once from the
            //    OpenLab Control Panel). EstablishConnection takes them as strings.
            ic = new InstrumentController();
            ic.AppInitialized += (s, e) => appInit.Set();
            ic.InstrumentStateChangeEvent += (s, e) =>
            {
                if (e.State != InstrumentState.Unknown) stateRecv.Set();
            };

            ic.EstablishConnection(cfg.ConnectionString ?? "", ticket,
                                   cfg.InstrumentId, cfg.ProjectId);

            var timeout = TimeSpan.FromSeconds(cfg.ConnectTimeoutSec);
            if (!appInit.WaitOne(timeout) || !stateRecv.WaitOne(timeout))
                throw new Exception("instrument connection not established within "
                                    + cfg.ConnectTimeoutSec + "s");
        }

        static string ResolveModuleKey(string match)
        {
            // ic.Modules: each module exposes Hashkey + a name. TODO confirm whether the
            // name property is .Name or .DisplayName on your assembly version.
            var mod = ic.Modules.FirstOrDefault(m =>
                (m.Name ?? "").IndexOf(match, StringComparison.OrdinalIgnoreCase) >= 0);
            if (mod == null) throw new Exception("module not found matching: " + match);
            return mod.Hashkey;
        }

        static void WireEvents()
        {
            ic.InstrumentStateChangeEvent += (s, e) => Emit("EVENT STATE " + e.State);
            ic.RunRecordChanged += (s, e) =>
            {
                var rec = e.UpdatedRecord;                       // RunRecordUpdate
                Emit("EVENT RUN " + rec.Id + " " + rec.Status);
                if (rec.Status == RunRecordStatus.Completed)
                    Emit("RESULT " + rec.Id + " " + rec.ResultFilePath);  // TODO confirm member
            };
        }

        // ---------------------------------------------------------------- dispatch
        static void DispatchLoop()
        {
            string line;
            while ((line = Console.ReadLine()) != null)
            {
                line = line.Trim();
                if (line.Length == 0) continue;

                int sp = line.IndexOf(' ');
                string verb = sp < 0 ? line : line.Substring(0, sp);
                string rest = sp < 0 ? "" : line.Substring(sp + 1);

                try
                {
                    switch (verb)
                    {
                        case "PING":      Emit("OK pong"); break;
                        case "SET_VALVE": HandleSetValve(rest); break;
                        case "SET_PARAM": HandleSetParam(rest); break;
                        case "START_RUN": HandleStartRun(rest); break;
                        case "ABORT":     ic.AbortCurrentSingleOrSequenceRun("client abort"); Emit("OK"); break;
                        case "STATUS":    Emit("OK " + ic.GetInstrumentStateInfoAsync().Result.InstrumentState); break;
                        case "QUIT":      Emit("OK bye"); return;
                        default:          Emit("ERR unknown command " + verb); break;
                    }
                }
                catch (Exception ex)
                {
                    Emit("ERR " + ex.Message);
                }
            }
        }

        static void HandleSetValve(string pos)
        {
            string fw;
            if (!cfg.ValveFirmware.TryGetValue(pos, out fw))
            {
                Emit("ERR unknown valve position " + pos);
                return;
            }
            // ExecuteFirmwareCommandAsync requires TakeInstrumentControl (done at startup).
            FirmwareCommandResult r = ic.ExecuteFirmwareCommandAsync(valveModuleKey, fw).Result;
            Emit("OK " + r.Response);
        }

        static void HandleSetParam(string token)
        {
            var kv = token.Split(new[] { '=' }, 2);             // name=value
            if (kv.Length != 2) { Emit("ERR malformed SET_PARAM"); return; }

            ParamMap pm;
            if (!cfg.ParamMap.TryGetValue(kv[0], out pm))
            {
                Emit("ERR param not allowed " + kv[0]);
                return;
            }

            string modKey = ResolveModuleKey(pm.ModuleMatch);
            if (!pending.ContainsKey(modKey))
                pending[modKey] = new List<ResourceIdAndValue>();
            pending[modKey].Add(new ResourceIdAndValue { Id = pm.PropId, Value = kv[1] });
            Emit("OK");
        }

        static void HandleStartRun(string json)
        {
            JObject a = JObject.Parse(json);
            string method     = (string)a["method"];
            string processing = (string)a["processing"];
            string vial       = (string)a["vial"];
            string result     = (string)a["result"];
            double injvol     = a["injvol"] != null ? (double)a["injvol"] : 0.0;

            var ext = ic.InjectionSources.FirstOrDefault(x => x.Id == "External");
            if (ext == null) { Emit("ERR external injection source not available"); return; }

            // Deep overrides (if any): load base -> set props -> save a per-run copy.
            string runMethod = method;
            if (pending.Count > 0)
            {
                ic.LoadAcquisitionMethod(method, true);
                foreach (var kvp in pending)
                {
                    ResourceResultWithString[] res;
                    ic.SetMethodResourceProperties(kvp.Key, kvp.Value.ToArray(), out res);
                }
                runMethod = result + ".amx";
                ic.SaveAsAcquisitionMethodNoOverwrite(runMethod, "RoboChem per-run override");
                pending.Clear();
            }

            // Validate against the instrument before committing.
            string err;
            if (!ic.ValidateSampleLocation(ext, vial, out err)) { Emit("ERR " + err); return; }
            if (!ic.ValidateInjectionVolume(ext, injvol, vial, runMethod, out err)) { Emit("ERR " + err); return; }

            var p = new SingleRunParams
            {
                AcquisitionMethod = runMethod,
                ProcessingMethod  = processing,
                SelectedInjection = ext,
                SampleLocation    = vial,
                InjectionVolume   = injvol,
                UseMethodInjectionVolume = false,
                ResultPath        = result,
            };

            RunSubmissionResult sub = ic.SubmitSingleRun(p);
            Emit("OK " + sub.RunId);    // TODO confirm member (run id used to match EVENT/RESULT)
        }

        // ---------------------------------------------------------------- output
        static void Emit(string s)
        {
            lock (ConsoleLock)
            {
                Console.WriteLine(s);
                Console.Out.Flush();
            }
        }
    }

    // ------------------------------------------------------------------- config types
    internal class ParamMap
    {
        public string ModuleMatch;   // substring of the module name (resolved to hashkey at runtime)
        public string PropId;        // resource property id (from the discovery script)
    }

    internal class ShimConfig
    {
        public string ConnectionString;     // "" => localhost OLSS (Workstation)
        public string Login;
        public string Domain;               // "" for internal auth
        public string Password;
        public string InstrumentId;         // GUID from OpenLab Control Panel
        public string ProjectId;            // GUID from OpenLab Control Panel
        public int ConnectTimeoutSec = 90;

        public string ValveModuleMatch = "Column";                  // name substring of the G7116
        public Dictionary<string, string> ValveFirmware =          // logical pos -> firmware cmd
            new Dictionary<string, string>();
        public Dictionary<string, ParamMap> ParamMap =             // logical param -> module+propId
            new Dictionary<string, ParamMap>();
    }
}
