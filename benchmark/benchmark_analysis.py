import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from matplotlib.patches import Patch
from datetime import datetime
import sys

def calculate_session_duration(df):
    """Calculate session duration in seconds"""
    # Sort by session_id and timestamp
    df_sorted = df.sort_values(['session_id', 'timestamp'])
    
    # Group by session_id and calculate duration
    session_durations = {}
    for session_id, group in df_sorted.groupby('session_id'):
        first_time = pd.to_datetime(group['timestamp'].iloc[0])
        last_time = pd.to_datetime(group['timestamp'].iloc[-1])
        session_durations[session_id] = (last_time - first_time).total_seconds()
    
    return session_durations

def create_box_plot_with_outlier_control(data_dict, var_name, output_file, 
                                          show_outliers=True, log_scale=False, 
                                          ylim_percentile=None):
    """
    Create box plot with options to control outlier display
    
    Parameters:
    - data_dict: Dictionary mapping treatment names to data arrays
    - var_name: Name of the variable being plotted
    - output_file: Path to save the plot
    - show_outliers: If False, outliers will be hidden
    - log_scale: If True, use log scale for y-axis
    - ylim_percentile: If provided (e.g., 95), set y-axis limit to this percentile of data
    """
    plt.figure(figsize=(14, 9))
    
    # Prepare data with custom treatment order
    treatment_order = ['grep', 'ripgrep', 'ragex']
    all_treatments = list(data_dict.keys())
    # Use custom order, but only include treatments that actually exist
    treatments = [t for t in treatment_order if t in all_treatments]
    data_for_plot = [data_dict[t] for t in treatments]
    positions = list(range(1, len(treatments) + 1))
    
    # Define colors
    colors = {'ragex': '#3498db', 'ripgrep': '#2ecc71', 'grep': '#e74c3c'}
    
    # Create box plot
    bp = plt.boxplot(data_for_plot, positions=positions, patch_artist=True,
                    notch=True, showmeans=True, widths=0.6,
                    showfliers=show_outliers)
    
    # Style the box plots
    for patch, treatment in zip(bp['boxes'], treatments):
        patch.set_facecolor(colors.get(treatment, '#95a5a6'))
        patch.set_alpha(0.7)
    
    # Customize means
    for mean in bp['means']:
        mean.set_marker('D')
        mean.set_markerfacecolor('darkred')
        mean.set_markersize(10)
    
    # Set labels and title
    plt.xticks(positions, treatments, fontsize=14)
    title = f'{var_name.replace("_", " ").title()}'
    if not show_outliers:
        title += ' (Outliers Hidden)'
    if log_scale:
        title += ' (Log Scale)'
    plt.title(title, fontsize=18, fontweight='bold', pad=25)
    plt.xlabel('Treatment', fontsize=16, labelpad=15)
    plt.ylabel(var_name.replace('_', ' ').title(), fontsize=16, labelpad=15)
    
    # Apply log scale if requested
    if log_scale:
        plt.yscale('log')
    
    # Set y-axis limits based on percentile if requested
    if ylim_percentile is not None:
        all_data = np.concatenate(data_for_plot)
        y_max = np.percentile(all_data, ylim_percentile)
        y_min = np.min(all_data) * 0.9
        plt.ylim(y_min, y_max * 1.1)
    
    plt.grid(True, alpha=0.3, axis='y')
    
    # Add statistics annotations with more spacing
    y_range = plt.ylim()[1] - plt.ylim()[0]
    for i, (pos, treatment) in enumerate(zip(positions, treatments)):
        data = data_dict[treatment]
        n = len(data)
        mean = np.mean(data)
        median = np.median(data)
        std = np.std(data)
        
        # Add sample size above plot
        # y_top = plt.ylim()[1] + y_range*0.05
        # plt.text(pos, y_top, f'n={n}', ha='center', va='bottom', 
        #         fontsize=12, fontweight='bold')
        
        # Add summary stats below plot with more spacing
        if not log_scale:
            stats_text = f'μ={mean:.1f}\nσ={std:.1f}'
            y_bottom = plt.ylim()[0] - y_range*0.2
        else:
            stats_text = f'μ={mean:.1f}'
            y_bottom = plt.ylim()[0] * 0.7
        
        plt.text(pos, y_bottom, stats_text, ha='center', va='top', 
                fontsize=11, style='italic')
    
    # Add legend with more padding
    legend_patches = [Patch(color=colors.get(t, '#95a5a6'), label=t, alpha=0.7) 
                     for t in treatments]
    plt.legend(handles=legend_patches, loc='upper right', title='Treatments',
              fontsize=12, title_fontsize=14, framealpha=0.9)
    
    # Add note about plot elements
    plt.figtext(0.5, 0.02, 
               'Box: IQR | Notch: 95% CI of median | Diamond: Mean | Line: Median', 
               ha='center', fontsize=11, style='italic', color='gray')
    
    # Add extra padding
    plt.tight_layout(pad=3.0)
    plt.subplots_adjust(top=0.92, bottom=0.12, left=0.1, right=0.95)
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    #plt.show()

def analyze_experiment_data_improved(csv_file):
    """Improved analysis with outlier control and timing metrics"""
    
    # Load the data
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print("Data Overview:")
    print(f"- Total rows: {len(df)}")
    # Show treatments in custom order
    treatment_order = ['grep', 'ripgrep', 'ragex']
    existing_treatments = [t for t in treatment_order if t in df['treatment'].unique()]
    print(f"- Unique treatments: {existing_treatments}")
    print(f"- Sessions per treatment:")
    print(df.groupby('treatment')['session_id'].nunique())
    
    # Calculate session durations
    session_durations = calculate_session_duration(df)
    
    # Get final values
    df_sorted = df.sort_values(['session_id', 'timestamp'])
    final_values = df_sorted.groupby('session_id').last().reset_index()
    
    # Add treatment and duration
    treatment_map = df.groupby('session_id')['treatment'].first()
    final_values['treatment'] = final_values['session_id'].map(treatment_map)
    final_values['session_duration'] = final_values['session_id'].map(session_durations)
    
    # Define variables including the new timing metric
    dependent_vars = ['cache_creation_input_tokens', 'cache_read_input_tokens', 
                      'output_tokens',
                      'session_duration']
    # dependent_vars = ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 
    #                   'output_tokens', 'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens',
    #                   'session_duration']
    
    # Define custom treatment order
    treatment_order = ['grep', 'ripgrep', 'ragex']
    all_treatments = final_values['treatment'].unique()
    # Use custom order, but only include treatments that actually exist in the data
    treatments = [t for t in treatment_order if t in all_treatments]
    colors = {'ragex': '#3498db', 'ripgrep': '#2ecc71', 'grep': '#e74c3c'}
    
    # Create plots for each variable with outlier control
    for var in dependent_vars:
        # Prepare data by treatment
        data_dict = {}
        for treatment in treatments:
            data_dict[treatment] = final_values[final_values['treatment'] == treatment][var].values
        
        # Standard plot with outliers
        create_box_plot_with_outlier_control(
            data_dict, var, 
            f'outputs/{var}_boxplot_standard.png',
            show_outliers=True
        )
        
        # For variables with large outliers, create additional views
        if var == 'cache_read_input_tokens':
            # Without outliers
            create_box_plot_with_outlier_control(
                data_dict, var, 
                f'outputs/{var}_boxplot_no_outliers.png',
                show_outliers=False
            )
            
            # With 95th percentile limit
            create_box_plot_with_outlier_control(
                data_dict, var, 
                f'outputs/{var}_boxplot_95percentile.png',
                show_outliers=True,
                ylim_percentile=95
            )
            
            # Log scale
            create_box_plot_with_outlier_control(
                data_dict, var, 
                f'outputs/{var}_boxplot_log.png',
                show_outliers=True,
                log_scale=True
            )
    
    # Create comprehensive summary plot with more spacing
    n_vars = len(dependent_vars)
    n_cols = 2
    n_rows = int(np.ceil(n_vars / n_cols))
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 6*n_rows))
    fig.subplots_adjust(hspace=0.4, wspace=0.3, top=0.94, bottom=0.06, left=0.08, right=0.95)
    
    axes = axes.flatten() if n_vars > 1 else [axes]
    
    for idx, var in enumerate(dependent_vars):
        ax = axes[idx]
        
        # Prepare data with custom treatment order
        data_for_plot = []
        for treatment in treatments:
            treatment_data = final_values[final_values['treatment'] == treatment][var].values
            data_for_plot.append(treatment_data)
        
        # Create box plot
        bp = ax.boxplot(data_for_plot, tick_labels=treatments, patch_artist=True,
                       notch=True, showmeans=True)
        
        # Style the box plots
        for patch, treatment in zip(bp['boxes'], treatments):
            patch.set_facecolor(colors.get(treatment, '#95a5a6'))
            patch.set_alpha(0.7)
        
        # Customize the plot
        title = var.replace("_", " ").title()
        if var == 'session_duration':
            title = 'Session Duration'
            y_label = "Duration [s]"
        else:
            y_label = "Tokens"
        ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
        ax.set_xlabel('Treatment', fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.set_ylim(bottom=max(0, ax.get_ylim()[0]))
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add sample sizes
        for i, treatment in enumerate(treatments):
            n = len(final_values[final_values['treatment'] == treatment])
            ax.text(i+1, ax.get_ylim()[1]*0.95, f'n={n}', 
                   ha='center', va='top', fontsize=10)
    
    # Remove any extra subplots
    for idx in range(len(dependent_vars), len(axes)):
        fig.delaxes(axes[idx])
    
    plt.suptitle('Final Values by Treatment - All Variables', fontsize=20, fontweight='bold', y=1.02)
    plt.savefig('outputs/all_variables_summary_improved.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Generate detailed statistics report
    with open('outputs/experiment_statistics_improved.txt', 'w') as f:
        f.write("IMPROVED EXPERIMENT ANALYSIS REPORT\n")
        f.write("="*60 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n")
        
        for var in dependent_vars:
            f.write(f"\n\n{var.upper().replace('_', ' ')}:\n")
            f.write("-"*40 + "\n")
            
            for treatment in treatments:
                data = final_values[final_values['treatment'] == treatment][var]
                if len(data) > 0:
                    f.write(f"\n{treatment}:\n")
                    f.write(f"  Count: {len(data)}\n")
                    f.write(f"  Mean: {data.mean():.2f}\n")
                    f.write(f"  Std Dev: {data.std():.2f}\n")
                    f.write(f"  Min: {data.min():.2f}\n")
                    f.write(f"  25th percentile: {data.quantile(0.25):.2f}\n")
                    f.write(f"  Median: {data.median():.2f}\n")
                    f.write(f"  75th percentile: {data.quantile(0.75):.2f}\n")
                    f.write(f"  Max: {data.max():.2f}\n")
                    
                    # Add outlier analysis for cache_read_input_tokens
                    if var == 'cache_read_input_tokens':
                        q1, q3 = data.quantile(0.25), data.quantile(0.75)
                        iqr = q3 - q1
                        outliers = data[(data < q1 - 1.5*iqr) | (data > q3 + 1.5*iqr)]
                        f.write(f"  Number of outliers: {len(outliers)}\n")
                        if len(outliers) > 0:
                            f.write(f"  Outlier values: {outliers.tolist()}\n")
    
    print("\nAnalysis complete! Files saved:")
    print("- Standard box plots: *_boxplot_standard.png")
    print("- Special views for cache_read_input_tokens:")
    print("  - Without outliers: cache_read_input_tokens_boxplot_no_outliers.png")
    print("  - 95th percentile: cache_read_input_tokens_boxplot_95percentile.png")
    print("  - Log scale: cache_read_input_tokens_boxplot_log.png")
    print("- Summary plot: all_variables_summary_improved.png")
    print("- Statistics report: experiment_statistics_improved.txt")
    
    return final_values

# Run the analysis
if __name__ == "__main__":
    if len(sys.argv)==2:
        final_values = analyze_experiment_data_improved(sys.argv[1])
    else:
        print("Wrong number of arguments")
