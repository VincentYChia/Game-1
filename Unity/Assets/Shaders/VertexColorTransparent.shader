// ============================================================================
// Game1 Vertex Color Transparent Shader
// Renders semi-transparent surfaces (water) with Standard lighting.
// Compatible with Built-in Render Pipeline (Surface Shader).
// URP compatibility: Unity auto-upgrades surface shaders in URP mode.
// ============================================================================

Shader "Game1/VertexColorTransparent"
{
    Properties
    {
        _Color ("Color", Color) = (0.12, 0.45, 0.82, 0.85)
        _Glossiness ("Smoothness", Range(0,1)) = 0.85
        _Metallic ("Metallic", Range(0,1)) = 0.1
    }

    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" }
        LOD 200
        ZWrite Off
        Blend SrcAlpha OneMinusSrcAlpha

        CGPROGRAM
        #pragma surface surf Standard alpha:fade
        #pragma target 3.0

        fixed4 _Color;
        half _Glossiness;
        half _Metallic;

        struct Input
        {
            float2 uv_MainTex;
        };

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            o.Albedo = _Color.rgb;
            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            o.Alpha = _Color.a;
        }
        ENDCG
    }

    FallBack "Transparent/Diffuse"
}
