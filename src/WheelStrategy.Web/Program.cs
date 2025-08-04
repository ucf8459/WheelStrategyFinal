using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Configuration;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Services;
using WheelStrategy.IBKR.Services;
using WheelStrategy.Web.Hubs;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddSignalR();

// Configure options
builder.Services.Configure<WheelStrategyOptions>(
    builder.Configuration.GetSection(WheelStrategyOptions.SectionName));

            // Register services
            builder.Services.AddScoped<IMarketDataService, IBKRTwsApiService>(); // Using official IBKR TWS API
            builder.Services.AddScoped<ITradeExecutor, TradeExecutor>();
            builder.Services.AddSingleton<IBKRConnectionService>(); // Changed to Singleton for persistent connection
            builder.Services.AddScoped<IWheelScanner, WheelScanner>();
            builder.Services.AddScoped<IWheelMonitor, WheelMonitor>();
            builder.Services.AddScoped<IAlertManager, AlertManager>();
            builder.Services.AddScoped<IDecisionSupportService, DecisionSupportService>();
            
            // Register HttpClient for IBKR Client Portal API (keeping for future use)
            builder.Services.AddHttpClient<IBKRWebApiService>(client =>
            {
                client.BaseAddress = new Uri("https://localhost:5001/v1/portal/");
                client.Timeout = TimeSpan.FromSeconds(30);
            });

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseDeveloperExceptionPage();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseCors("AllowAll");

app.MapControllers();
app.MapHub<DashboardHub>("/dashboardHub");

// Serve the dashboard as the default page
app.MapGet("/", async context =>
{
    context.Response.Redirect("/index.html");
});

app.Run(); 