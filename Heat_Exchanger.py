import streamlit as st
import CoolProp.CoolProp as CP
import math

# --- PAGE CONFIG (This fills the screen better) ---
st.set_page_config(layout="wide") 

# --- SIDEBAR: Project Identification ---
with st.sidebar:
    st.header("📋 Project Identification")
    tag_no = st.text_input("Exchanger Tag No.", value="HEX-101")
    hex_name = st.text_input("Exchanger Name / Service", value="Process Cooler")
    st.divider()
    st.info("Fill in the process data in the main panel to calculate duty.")
    # You can also add a small logo here:
    # st.image("your_logo_url") 

# --- CONSTANTS (Required for Step 1 Fallback) ---
FLUID_PROPS = {
    "Water": {"cp": 4.18, "latent": 2257},
    "Methanol": {"cp": 2.53, "latent": 1100},
    "Benzene": {"cp": 1.74, "latent": 394},
    "Ethanol": {"cp": 2.44, "latent": 841},
    "Acetone": {"cp": 2.15, "latent": 518},
}

FLUID_MAP = {
    "Water": "Water",
    "Methanol": "Methanol",
    "Benzene": "Benzene",
    "Ethanol": "Ethanol",
    "Acetone": "Acetone",
    "Custom": None
}

st.title("🛡️ HEX Designer: Energy Balance Pro (NIST Powered)")

# --- IDENTIFICATION ---


# --- STEP 1: PROCESS FLUID ANALYSIS (Updated with Pressure) ---
st.subheader("Step 1: Process Fluid Analysis")
p1, p2, p3, p4 = st.columns(4) # Added 4th column for Pressure

p_fluid = p1.selectbox("Process Fluid", list(FLUID_MAP.keys()))
m_process = p2.number_input("Process Mass Flow (kg/h)", value=5000.0)
phase_change = p3.radio("Phase Change?", ["No", "Yes"], horizontal=True)
p_abs = p4.number_input("Operating Pressure (bar a)", value=1.013, help="Absolute pressure affects boiling point and properties.")

t1 = p1.number_input("Inlet Temp (°C)", value=90.0)
t2 = p2.number_input("Outlet Temp (°C)", value=60.0)
# --- STEP 1: PROCESS FLUID ANALYSIS ---
# ... (your selectbox and number_inputs for t1, t2) ...

# ADD THIS LINE TO DEFINE 'role' FOR STEP 2
role = "Hot Stream (Being Cooled)" if t1 > t2 else "Cold Stream (Being Heated)"

# ... (the rest of your CoolProp logic) ...


# Convert bar to Pascal for CoolProp
p_pa = p_abs * 100000

cp_val, lat_val, prop_source = 0.0, 0.0, "Static Database"

if p_fluid != "Custom":
    try:
        fluid_id = FLUID_MAP[p_fluid]
        # 1. Calculate CP at T2 and Operating Pressure
        cp_val = CP.PropsSI('C', 'T', t2 + 273.15, 'P', p_pa, fluid_id) / 1000 
        
        if phase_change == "Yes":
            # 2. Get Saturation Temperature at this Pressure
            t_sat_k = CP.PropsSI('T', 'P', p_pa, 'Q', 0, fluid_id)
            t_sat_c = t_sat_k - 273.15
            st.caption(f"ℹ️ Saturation Temp at {p_abs} bar: {t_sat_c:.2f} °C")
            
            # 3. Calculate Latent Heat (H_vapor - H_liquid) at this Pressure
            h_l = CP.PropsSI('H', 'P', p_pa, 'Q', 0, fluid_id) 
            h_v = CP.PropsSI('H', 'P', p_pa, 'Q', 1, fluid_id) 
            lat_val = abs(h_v - h_l) / 1000 
        
        prop_source = f"NIST (CoolProp) @ {t2}°C, {p_abs} bar"
    except Exception as e:
        st.error(f"CoolProp Error: {e}. Using fallback values.")
        cp_val = FLUID_PROPS[p_fluid]["cp"]
        lat_val = FLUID_PROPS[p_fluid]["latent"] if phase_change == "Yes" else 0.0
else:
    cp_val = p3.number_input("Enter Custom Cp (kJ/kg·K)", value=1.0)
    lat_val = st.number_input("Enter Custom Latent Heat (kJ/kg)", value=0.0) if phase_change == "Yes" else 0.0

# --- HEAT DUTY CALCULATION ---
st.write(f"📊 **Fluid Properties:** Source: `{prop_source}`")
c_edit1, c_edit2 = st.columns(2)
cp_final = c_edit1.number_input("Specific Heat Cp (kJ/kg·K)", value=float(cp_val))

if phase_change == "Yes":
    lat_final = c_edit2.number_input("Latent Heat λ (kJ/kg)", value=float(lat_val))
    # Logic: Sensible heat to reach T_sat + Latent Heat + Sensible heat from T_sat to T2
    # Simplified here as Sensible + Latent:
    sensible_kw = (m_process * cp_final * abs(t1 - t2)) / 3600
    latent_kw = (m_process * lat_final) / 3600
    duty_kw = sensible_kw + latent_kw
else:
    duty_kw = (m_process * cp_final * abs(t1 - t2)) / 3600

st.metric("Total Process Heat Duty (Q)", f"{duty_kw:.2f} kW")


# --- STEP 2: UTILITY BALANCING ---
st.subheader("Step 2: Utility Stream Calculation")
u_col1, u_col2 = st.columns(2)

u_mode = u_col1.radio("What do you want to calculate for the Utility?", 
                      ["Utility Flow Rate", "Utility Outlet Temperature"])

if role == "Hot Stream (Being Cooled)":
    u_type = u_col1.selectbox("Select Cold Utility", ["Cooling Water", "Chilled Water"])
    u_cp = 4.187 # Default for water
else:
    u_type = u_col1.selectbox("Select Hot Utility", ["Steam", "Hot Water", "Thermic Oil"])
    u_cp = 4.187 if "Water" in u_type else 2.1 # Simplified for oil

if u_type == "Steam":
    p_steam = u_col2.number_input("Steam Pressure (bar a)", value=3.0)
    latent_s = STEAM_TABLE.get(round(p_steam, 0), 2163)
    m_steam = (duty_kw * 3600) / latent_s
    st.metric("Required Steam Flow", f"{m_steam:.2f} kg/h")
    u_t_in = u_t_out = 133.5 # Temp at 3 bar a for LMTD later
else:
    u_t_in = u_col2.number_input("Utility Inlet Temp (°C)", value=30.0 if "Cold" in role else 150.0)
    
    if u_mode == "Utility Flow Rate":
        u_t_out = u_col2.number_input("Utility Outlet Temp (°C)", value=40.0 if "Cold" in role else 130.0)
        # Flow = Q / (Cp * dT)
        if abs(u_t_out - u_t_in) > 0:
            m_util = (duty_kw * 3600) / (u_cp * abs(u_t_out - u_t_in))
            st.metric(f"Required {u_type} Flow", f"{m_util:.2f} kg/h")
        else:
            st.error("ΔT cannot be zero for sensible heat utility.")
    else:
        m_util = u_col2.number_input(f"Fixed {u_type} Flow (kg/h)", value=10000.0)
        # dT = Q / (m * Cp)
        dt_util = (duty_kw * 3600) / (m_util * u_cp)
        u_t_out = u_t_in + dt_util if "Cold" in role else u_t_in - dt_util
        st.metric(f"Utility Outlet Temp", f"{u_t_out:.2f} °C")

# --- STEP 3: LMTD & TEMPERATURE PROFILE ---
st.divider()
st.subheader("Step 3: Temperature Profile & LMTD")

flow_type = st.radio("Select Flow Configuration:", ["Counter-Current", "Co-Current"], horizontal=True)

if 'lmtd' not in st.session_state:
    st.session_state.lmtd = None

if st.button("Calculate LMTD & Profile"):
    t_h_in, t_h_out = (t1, t2) if t2 < t1 else (u_t_in, u_t_out)
    t_c_in, t_c_out = (u_t_in, u_t_out) if t2 < t1 else (t1, t2)

    dt1 = t_h_in - t_c_out if flow_type == "Counter-Current" else t_h_in - t_c_in
    dt2 = t_h_out - t_c_in if flow_type == "Counter-Current" else t_h_out - t_c_out

    if dt1 <= 0 or dt2 <= 0:
        st.error("⚠️ Temperature Cross Detected!")
        st.session_state.lmtd = None
    else:
        st.session_state.lmtd = (dt1 - dt2) / math.log(dt1 / dt2) if dt1 != dt2 else dt1

# This keeps LMTD visible even when Step 4 is edited
if st.session_state.lmtd:
    st.info(f"✅ **LMTD for Calculation:** {st.session_state.lmtd:.2f} °C")

# --- STEP 4: SURFACE AREA & U-VALUE ---
st.divider()
st.subheader("Step 4: Surface Area & U-Value Estimation")

def get_suggested_u(proc, util):
    if proc == "Custom" or "Custom" in str(util): return None
    mapping = {
        "Water": {"Cooling Water": 1000, "Steam": 2000, "Hot Water": 900, "Chilled Water": 1000},
        "Methanol": {"Cooling Water": 600, "Steam": 800},
        "Benzene": {"Cooling Water": 500, "Steam": 750},
    }
    return mapping.get(proc, {}).get(util, 500.0)

s_u = get_suggested_u(p_fluid, u_type)
u_col1, u_col2 = st.columns(2)

if "manual_u_mode" not in st.session_state:
    st.session_state.manual_u_mode = False

if s_u is None:
    st.session_state.manual_u_mode = True
    u_col1.warning("⚠️ Custom fluid: Enter U-Value manually.")
else:
    # Increased Font Size for Suggested U
    u_col1.markdown(f"### Suggested U: `{s_u}` W/m²·K")
    if u_col1.button("Edit U-Value Manually"):
        st.session_state.manual_u_mode = True

if st.session_state.manual_u_mode:
    u_design = u_col1.number_input("Design U-Value (W/m²·K)", value=float(s_u) if s_u else 500.0)
else:
    u_design = float(s_u)

if st.session_state.lmtd:
    area_req = (duty_kw * 1000) / (u_design * st.session_state.lmtd)
    overdesign = u_col2.slider("Overdesign (%)", 0, 50, 10)
    final_area_req = area_req * (1 + overdesign/100)
    u_col2.metric("Target Design Area", f"{final_area_req:.2f} m²")
else:
    st.warning("Please calculate LMTD first.")

# --- STEP 5: TUBE & SHELL GEOMETRY (MANUAL ITERATION) ---
st.divider()
st.subheader("Step 5: Tube & Shell Sizing (The Physical Check)")

if st.session_state.lmtd:
    # 1. Fluid Allocation
    st.info("🔄 **Fluid Allocation:** Which fluid flows through the TUBES?")
    tube_side_fluid = st.radio("Select Tube-Side Fluid:", ["Process Fluid", "Utility Stream"], horizontal=True)
    
    g1, g2, g3 = st.columns(3)
    t_od_mm = g1.selectbox("Tube OD (mm)", [12.7, 15.87, 19.05, 25.4], index=2)
    t_len = g2.number_input("Tube Length (m)", value=3.0)
    
    # Calculation for Suggestion Only
    area_per_tube = math.pi * (t_od_mm / 1000) * t_len
    # Use final_area_req from your previous step
    suggested_n = math.ceil(final_area_req / area_per_tube)
    
    # 2. Manual Tube Entry
    st.write(f"💡 *Suggestion to meet target area: **{suggested_n} tubes***")
    n_tubes = g3.number_input("Actual Number of Tubes to Install", value=int(suggested_n), step=1)
    
    if n_tubes > 0:
        actual_area = n_tubes * area_per_tube
        st.metric("Actual Heat Transfer Area", f"{actual_area:.2f} m²")
        
        # 3. Sufficiency Logic
        diff_pct = ((actual_area / final_area_req) - 1) * 100
        if actual_area >= final_area_req:
            st.success(f"✅ Area is Sufficient ({diff_pct:.1f}% Excess)")
        else:
            st.error(f"⚠️ Area is Insufficient ({abs(diff_pct):.1f}% Shortfall)")
            st.warning("Your physical design provides less area than required by the Assumed U-Value.")
            is_acceptable = st.checkbox("Accept this shortfall? (e.g., if you believe U-Value is actually higher)")
            if is_acceptable:
                st.info("User accepted shortfall. Proceeding with current geometry.")

        # 4. Physical Shell & Baffle Entry
        st.markdown("### 🛠️ Shell & Baffle Selection")
        
        # Calculate theoretical min for guidance
        pitch_ratio = 1.25
        min_shell_id = 0.637 * math.sqrt(n_tubes * (pitch_ratio**2) * ((t_od_mm/1000)**2)) * 1000
        
        c1, c2 = st.columns(2)
        # USER INPUT: Actual Shell Diameter
        actual_shell_dia = c1.number_input(
            "Actual Shell ID (mm)", 
            value=int(min_shell_id), 
            help=f"Theoretical minimum is ~{int(min_shell_id)} mm. Enter standard pipe size."
        )
        
        # USER INPUT: Baffle Spacing
        actual_baffle_space = c2.number_input(
            "Baffle Spacing (mm)", 
            value=int(actual_shell_dia * 0.4), 
            help="Adjust this to balance Pressure Drop vs Heat Transfer."
        )

        # 5. U-Value Back-Calculation
        u_required_for_this_area = (duty_kw * 1000) / (actual_area * st.session_state.lmtd)
        
        st.markdown(f"### 🔍 Design Validation")
        st.write(f"To make this work, **Actual U** must be: **{u_required_for_this_area:.1f} W/m²·K**.")
        
        if u_required_for_this_area > u_design:
            st.warning(f"🚩 Required U is higher than assumed {u_design}. Check velocities!")
        else:
            st.success(f"✅ Design is safe (Conservative compared to assumed U).")

        # Store in session state for the Pressure Drop calculation step
        st.session_state.shell_dia = actual_shell_dia
        st.session_state.baffle_space = actual_baffle_space

else:
    st.warning("Complete LMTD and Area steps first.")

# --- STEP 7: DESIGN FOULING VALIDATION ---
st.divider()
st.subheader("Step 7: Design Fouling & Surface Margin")

if 'n_tubes' in locals() and n_tubes > 0:
    # 1. Define Design Fouling
    f_col1, f_col2 = st.columns(2)
    t_f_name = p_fluid if tube_side_fluid == "Process Fluid" else u_type
    s_f_name = u_type if tube_side_fluid == "Process Fluid" else p_fluid
    
    rf_t = f_col1.number_input(f"Design Rf - Tube ({t_f_name})", value=0.0002, format="%.5f")
    rf_s = f_col2.number_input(f"Design Rf - Shell ({s_f_name})", value=0.0002, format="%.5f")
    total_rf_design = rf_t + rf_s

    # 2. U-Value Calculations (Clean vs Dirty)
    # Dirty U is your assumed design U from Step 4
    u_dirty = u_design 
    
    # 1/Uc = 1/Ud - Rf  => Uc = 1 / ( (1/Ud) - Rf )
    if (1/u_dirty - total_rf_design) > 0:
        u_clean = 1 / (1/u_dirty - total_rf_design)
        
        # 3. Area Requirements
        area_clean_req = (duty_kw * 1000) / (u_clean * st.session_state.lmtd)
        area_dirty_req = (duty_kw * 1000) / (u_dirty * st.session_state.lmtd)
        
        st.markdown("### 📈 U-Value & Area Comparison")
        m1, m2, m3 = st.columns(3)
        m1.metric("U-Clean (Day 1)", f"{u_clean:.1f} W/m²·K")
        m2.metric("U-Dirty (Design)", f"{u_dirty:.1f} W/m²·K")
        m3.metric("Actual Area Provided", f"{actual_area:.2f} m²")

        # 4. Surface Margin (%) 
        # Margin = (Actual Area / Required Clean Area) - 1
        surface_margin = ((actual_area / area_clean_req) - 1) * 100
        
        # 5. Conditional Display (Green if Margin >= Design Fouling Requirement)
        if actual_area >= area_dirty_req:
            st.success(f"✅ **Positive Margin:** Your design has **{surface_margin:.1f}%** excess area. This is sufficient to handle the specified fouling.")
        else:
            st.error(f"❌ **Negative Margin:** Your design only has **{surface_margin:.1f}%** extra area, which is LESS than the {area_dirty_req:.2f} m² required for fouling.")
            
    else:
        st.warning("⚠️ **Calculation Error:** The Fouling Resistance is higher than the total Resistance (1/U). Please lower the Rf values or increase the Assumed U-Value in Step 4.")
else:
    st.info("💡 Enter the Number of Tubes in Step 5 to see the Fouling Analysis.")



# --- STEP 8: PRESSURE DROP (ΔP) & HYDRAULIC VALIDATION ---
st.divider()
st.subheader("Step 8: Pressure Drop (ΔP) & Hydraulic Validation")

PROPS_DB = {
    "Water": {"rho": 990, "mu": 0.0006},
    "Methanol": {"rho": 790, "mu": 0.00045},
    "Benzene": {"rho": 870, "mu": 0.0005},
    "Cooling Water": {"rho": 995, "mu": 0.0008},
    "Chilled Water": {"rho": 1000, "mu": 0.0012},
    "Thermic Oil": {"rho": 850, "mu": 0.005},
    "Steam": {"rho": 1.5, "mu": 0.000013}, 
    "Hot Water": {"rho": 980, "mu": 0.0005},
    "Custom": {"rho": 1000, "mu": 0.001}
}

# Ensure variables from Step 5/7 are accessible
if 'n_tubes' in locals() and n_tubes > 0:
    # 1. FLUID ALLOCATION MAPPING
    if tube_side_fluid == "Process Fluid":
        t_fluid_name, s_fluid_name = p_fluid, u_type
        m_t_kg_h = m_process
        m_s_kg_h = m_util if 'm_util' in locals() else 0
    else:
        t_fluid_name, s_fluid_name = u_type, p_fluid
        m_t_kg_h = m_util if 'm_util' in locals() else 0
        m_s_kg_h = m_process

    tp = PROPS_DB.get(t_fluid_name, PROPS_DB["Custom"])
    sp = PROPS_DB.get(s_fluid_name, PROPS_DB["Custom"])

    st.info(f"📍 **Allocation:** {t_fluid_name} (Tube Side) | {s_fluid_name} (Shell Side)")

    d_col1, d_col2 = st.columns(2)
    rho_t = d_col1.number_input(f"Density {t_fluid_name} (kg/m³)", value=float(tp["rho"]), key="rt_final")
    mu_t = d_col1.number_input(f"Viscosity {t_fluid_name} (Pa·s)", value=float(tp["mu"]), format="%.6f", key="mt_final")
    
    rho_s = d_col2.number_input(f"Density {s_fluid_name} (kg/m³)", value=float(sp["rho"]), key="rs_final")
    mu_s = d_col2.number_input(f"Viscosity {s_fluid_name} (Pa·s)", value=float(sp["mu"]), format="%.6f", key="ms_final")

    # 2. GEOMETRY & VELOCITY CALCULATIONS
    n_passes = d_col1.selectbox("Select Tube Passes", [1, 2, 4, 6, 8], index=1)
    t_id_m = (t_od_mm - 2.1) / 1000  # Internal Diameter
    
    # Tube Side
    area_per_pass = (n_tubes / n_passes) * (math.pi / 4) * (t_id_m**2)
    v_tube = (m_t_kg_h / 3600) / (rho_t * area_per_pass) if (area_per_pass > 0 and rho_t > 0) else 0
    
    # Shell Side (Using your Actual Shell Dia and Baffle Spacing)
    d_shell_m = actual_shell_dia / 1000
    b_space_m = actual_baffle_space / 1000
    pitch_m = (t_od_mm * 1.25) / 1000
    clearance_m = pitch_m - (t_od_mm / 1000)
    shell_area = d_shell_m * b_space_m * (clearance_m / pitch_m)
    v_shell = (m_s_kg_h / 3600) / (rho_s * shell_area) if (shell_area > 0 and rho_s > 0) else 0

    # 3. INTERMEDIATE BREAKDOWN DISPLAY
    st.markdown("### 📏 Intermediate Geometry & Velocity Breakdown")
    g_col1, g_col2, g_col3 = st.columns(3)
    g_col1.metric("Area per Pass (A_p)", f"{area_per_pass:.5f} m²")
    g_col2.metric("Tube Velocity (V_t)", f"{v_tube:.2f} m/s")
    g_col3.metric("Shell Velocity (V_s)", f"{v_shell:.2f} m/s")

    # 4. DESIGN GUIDANCE (TEMA RANGES)
    st.divider()
    if v_tube < 0.9:
        st.warning(f"💡 **Suggestion:** Velocity ({v_tube:.2f} m/s) is below 0.9 m/s. "
                   "Consider **increasing Tube Passes** to prevent fouling.")
    elif v_tube > 2.2:
        st.error(f"⚠️ **High Velocity Alert:** {v_tube:.2f} m/s exceeds 2.2 m/s. "
                 "Check if Pressure Drop is acceptable and watch for Erosion.")
    else:
        st.success(f"✅ **Optimal Velocity:** {v_tube:.2f} m/s is within the TEMA-recommended liquid range.")

    # 5. PRESSURE DROP CALCULATIONS
    # Tube Side
    re_t = (rho_t * v_tube * t_id_m) / mu_t if mu_t > 0 else 0
    f_t = 0.0014 + 0.125 * (re_t**-0.32) if re_t > 2100 else (64/re_t if re_t > 0 else 0)
    dp_t = (f_t * (t_len / t_id_m) * (rho_t * (v_tube**2) / 2) * n_passes) / 100000 
    
    # Shell Side (Kern)
    de_m = (4 * (pitch_m**2 * 0.866 / 2 - math.pi * (t_od_mm/1000)**2 / 8)) / (math.pi * (t_od_mm/1000) / 2)
    re_s = (rho_s * v_shell * de_m) / mu_s if mu_s > 0 else 0
    f_s = 0.5 * (re_s**-0.15) if re_s > 0 else 0
    dp_s = (f_s * (d_shell_m / de_m) * (rho_s * (v_shell**2) / 2) * (t_len / b_space_m)) / 100000

    # 6. RESULTS SUMMARY
    st.divider()
    res1, res2 = st.columns(2)
    res1.metric(f"Tube Side ΔP", f"{dp_t:.4f} bar", help=f"Fluid: {t_fluid_name} | Re: {int(re_t)}")
    res2.metric(f"Shell Side ΔP", f"{dp_s:.4f} bar", help=f"Fluid: {s_fluid_name} | Re: {int(re_s)}")

else:
    st.info("💡 Please complete Step 5 and Step 7 (Geometry) to view Hydraulic results.")




from fpdf import FPDF
import datetime

from fpdf import FPDF
import datetime

# --- STEP 9: FINAL SUMMARY & REPORT ---
st.divider()
st.subheader("Step 9: Final Design Summary")

# Professional Credit
st.markdown(f"<div style='text-align: right; color: #555;'>Developed by: <b>Dilip Kumar B.</b></div>", unsafe_allow_html=True)

# Session state to keep report visible after clicking download
if 'report_ready' not in st.session_state:
    st.session_state.report_ready = False

if st.button("📝 Generate Final Design Report Preview"):
    st.session_state.report_ready = True

if st.session_state.report_ready:
    
    # 1. Structure the Data (Matches your image exactly + Identification)
    final_report = [
        # IDENTIFICATION SECTION
        {"Sr. No": "-", "Section": "Identification", "Parameters": "Exchanger Tag No.", "Value": f"{tag_no}", "UOM": "-"},
        {"Sr. No": "-", "Section": "Identification", "Parameters": "Exchanger Name", "Value": f"{hex_name}", "UOM": "-"},
        
        # PROCESS DATA
        {"Sr. No": "1", "Section": "Process Data", "Parameters": "Fluid Allocation", "Value": f"{t_fluid_name} / {s_fluid_name}", "UOM": "Tube/Shell"},
        {"Sr. No": "2", "Section": "Process Data", "Parameters": "Total Heat duty", "Value": f"{duty_kw:.2f}", "UOM": "kW"},
        {"Sr. No": "3", "Section": "Process Data", "Parameters": "Mass flow", "Value": f"{m_t_kg_h:.1f} / {m_s_kg_h:.1f}", "UOM": "kg/h"},
        {"Sr. No": "4", "Section": "Process Data", "Parameters": "LMTD", "Value": f"{st.session_state.lmtd:.2f}", "UOM": "C"},
        
        # THERMAL DESIGN
        {"Sr. No": "5", "Section": "Thermal Design", "Parameters": "U-clean", "Value": f"{u_clean:.1f}", "UOM": "W/m2.K"},
        {"Sr. No": "6", "Section": "Thermal Design", "Parameters": "U-Dirty", "Value": f"{u_dirty:.1f}", "UOM": "W/m2.K"},
        {"Sr. No": "7", "Section": "Thermal Design", "Parameters": "Total Fouling resistance", "Value": f"{total_rf_design:.5f}", "UOM": "m2.K/W"},
        {"Sr. No": "8", "Section": "Thermal Design", "Parameters": "Surface Margin", "Value": f"{surface_margin:.1f}", "UOM": "%"},
        
        # HARDWARE
        {"Sr. No": "9", "Section": "Hardware", "Parameters": "Tube OD", "Value": f"{t_od_mm}", "UOM": "mm"},
        {"Sr. No": "10", "Section": "Hardware", "Parameters": "Tube Length", "Value": f"{t_len}", "UOM": "m"},
        {"Sr. No": "11", "Section": "Hardware", "Parameters": "Number of Tubes", "Value": f"{n_tubes}", "UOM": "Nos"},
        {"Sr. No": "12", "Section": "Hardware", "Parameters": "Shell Diameter (ID)", "Value": f"{int(actual_shell_dia)}", "UOM": "mm"},
        
        # HYDRAULICS
        {"Sr. No": "13", "Section": "Hydraulics", "Parameters": "Tube Velocity", "Value": f"{v_tube:.2f}", "UOM": "m/s"},
        {"Sr. No": "14", "Section": "Hydraulics", "Parameters": "Shell Velocity", "Value": f"{v_shell:.2f}", "UOM": "m/s"},
        {"Sr. No": "15", "Section": "Hydraulics", "Parameters": "Tube Side Pressure Drop (dP)", "Value": f"{dp_t:.3f}", "UOM": "bar"},
        {"Sr. No": "16", "Section": "Hydraulics", "Parameters": "Shell Side Pressure Drop (dP)", "Value": f"{dp_s:.3f}", "UOM": "bar"},
    ]

    # --- PREVIEW TABLE ---
    st.success(f"### 📊 Engineering Data Sheet: {tag_no}")
    st.table(final_report)

    # --- PDF GENERATION ---
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header Block
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(190, 12, "HEAT EXCHANGER DESIGN REPORT", ln=True, align="C")
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(190, 8, f"Equipment Tag: {tag_no}", ln=True, align="C")
        pdf.cell(190, 8, f"Service: {hex_name}", ln=True, align="C")
        
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(190, 8, f"Generated on: {datetime.date.today()} | Developed by Dilip Kumar B.", ln=True, align="C")
        pdf.ln(10)

        # Table Setup
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(220, 230, 245)
        pdf.set_text_color(0, 0, 0)
        
        # Column widths: SrNo(15), Section(40), Params(60), Value(40), UOM(35)
        w = [15, 40, 60, 40, 35]
        cols = ["Sr. No", "Section", "Parameters", "Value", "UOM"]
        
        for i, col in enumerate(cols):
            pdf.cell(w[i], 10, col, border=1, fill=True, align="C")
        pdf.ln()

        # Table Data
        pdf.set_font("Helvetica", "", 9)
        for row in final_report:
            # Highlight Section Names
            pdf.cell(w[0], 8, str(row["Sr. No"]), border=1, align="C")
            pdf.cell(w[1], 8, str(row["Section"]), border=1)
            pdf.cell(w[2], 8, str(row["Parameters"]), border=1)
            pdf.cell(w[3], 8, str(row["Value"]), border=1, align="C")
            pdf.cell(w[4], 8, str(row["UOM"]), border=1, align="C")
            pdf.ln()

        # PDF Footer Summary
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        if surface_margin >= 0:
            pdf.set_text_color(0, 128, 0) # Green
            pdf.cell(190, 10, f"RESULT: DESIGN IS THERMALLY SUFFICIENT (Margin: {surface_margin:.1f}%)", ln=True)
        else:
            pdf.set_text_color(200, 0, 0) # Red
            pdf.cell(190, 10, f"RESULT: DESIGN IS INSUFFICIENT (Deficit: {abs(surface_margin):.1f}%)", ln=True)

        # Save to Bytes
        pdf_bytes = pdf.output()

        # --- DOWNLOAD BUTTON ---
        st.download_button(
            label=f"📥 Download Official PDF for {tag_no}",
            data=bytes(pdf_bytes),
            file_name=f"Design_Report_{tag_no}.pdf",
            mime="application/pdf"
        )
        
    except Exception as e:
        st.error(f"Error creating PDF: {e}")

# --- GLOBAL FOOTER ---
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #888888; font-size: 0.85em;">
        🛡️ <b>HEX Designer: Energy Balance Pro v3.0</b><br>
        Built for Professional Process Validation<br>
        Developed by <b>Dilip Kumar B.</b>
    </div>
    """, 
    unsafe_allow_html=True
)
