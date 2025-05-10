# (Header, UAV_PROFILES, UI setup — unchanged...)

        if max_lift == 0 and payload_weight_g > 0:
            st.error("This UAV cannot carry payload. Please reduce payload weight to 0.")
            st.stop()

        load_ratio = payload_weight_g / max_lift if max_lift > 0 else 0
        if load_ratio < 0.7:
            efficiency_penalty = 1
        elif load_ratio < 0.9:
            efficiency_penalty = 1.1
        elif load_ratio <= 1.0:
            efficiency_penalty = 1.25
        else:
            efficiency_penalty = 1.4

        if drone_model != "Custom Build" and UAV_PROFILES[drone_model]["power_system"] == "Hybrid":
            total_draw = UAV_PROFILES[drone_model]["draw_watt"]
        else:
            total_draw = total_power_draw * efficiency_penalty

# (Remaining simulation logic follows unchanged...)
    
            

        
